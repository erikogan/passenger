# encoding: binary
#  Phusion Passenger - https://www.phusionpassenger.com/
#  Copyright (c) 2010-2013 Phusion
#
#  "Phusion Passenger" is a trademark of Hongli Lai & Ninh Bui.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#  THE SOFTWARE.

require 'socket'
require 'fcntl'
require 'phusion_passenger'
require 'phusion_passenger/constants'
require 'phusion_passenger/public_api'
require 'phusion_passenger/message_client'
require 'phusion_passenger/debug_logging'
require 'phusion_passenger/utils'
require 'phusion_passenger/utils/robust_interruption'
require 'phusion_passenger/utils/tmpdir'
require 'phusion_passenger/ruby_core_enhancements'
require 'phusion_passenger/request_handler/thread_handler'

module PhusionPassenger


class RequestHandler
	include DebugLogging
	include Utils
	
	# Signal which will cause the Rails application to exit immediately.
	HARD_TERMINATION_SIGNAL = "SIGTERM"
	# Signal which will cause the Rails application to exit as soon as it's done processing a request.
	SOFT_TERMINATION_SIGNAL = "SIGUSR1"
	BACKLOG_SIZE    = 500
	
	# String constants which exist to relieve Ruby's garbage collector.
	IGNORE              = 'IGNORE'              # :nodoc:
	DEFAULT             = 'DEFAULT'             # :nodoc:
	
	# A hash containing all server sockets that this request handler listens on.
	# The hash is in the form of:
	#
	#   {
	#      name1 => [socket_address1, socket_type1, socket1],
	#      name2 => [socket_address2, socket_type2, socket2],
	#      ...
	#   }
	#
	# +name+ is a Symbol. +socket_addressx+ is the address of the socket,
	# +socket_typex+ is the socket's type (either 'unix' or 'tcp') and
	# +socketx+ is the actual socket IO objec.
	# There's guaranteed to be at least one server socket, namely one with the
	# name +:main+.
	attr_reader :server_sockets

	attr_reader :concurrency
	
	# Specifies the maximum allowed memory usage, in MB. If after having processed
	# a request AbstractRequestHandler detects that memory usage has risen above
	# this limit, then it will gracefully exit (that is, exit after having processed
	# all pending requests).
	#
	# A value of 0 (the default) indicates that there's no limit.
	attr_accessor :memory_limit
	
	# The number of times the main loop has iterated so far. Mostly useful
	# for unit test assertions.
	attr_reader :iterations
	
	# If a soft termination signal was received, then the main loop will quit
	# the given amount of seconds after the last time a connection was accepted.
	# Defaults to 3 seconds.
	attr_accessor :soft_termination_linger_time
	
	# A password with which clients must authenticate. Default is unauthenticated.
	attr_accessor :connect_password
	
	# Create a new RequestHandler with the given owner pipe.
	# +owner_pipe+ must be the readable part of a pipe IO object.
	#
	# Additionally, the following options may be given:
	# - memory_limit: Used to set the +memory_limit+ attribute.
	# - detach_key
	# - connect_password
	# - pool_account_username
	# - pool_account_password_base64
	def initialize(owner_pipe, options = {})
		require_option(options, "app_group_name")
		install_options_as_ivars(self, options,
			"app",
			"app_group_name",
			"connect_password",
			"detach_key",
			"analytics_logger",
			"pool_account_username"
		)
		@thread_handler = options["thread_handler"] || ThreadHandler
		@concurrency = 1
		@memory_limit = options["memory_limit"] || 0
		if options["pool_account_password_base64"]
			@pool_account_password = options["pool_account_password_base64"].unpack('m').first
		end

		#############
		#############

		@server_sockets = {}
		
		if should_use_unix_sockets?
			@main_socket_address, @main_socket = create_unix_socket_on_filesystem
		else
			@main_socket_address, @main_socket = create_tcp_socket
		end
		@server_sockets[:main] = {
			:address     => @main_socket_address,
			:socket      => @main_socket,
			:protocol    => :session,
			:concurrency => @concurrency
		}

		@http_socket_address, @http_socket = create_tcp_socket
		@server_sockets[:http] = {
			:address     => @http_socket_address,
			:socket      => @http_socket,
			:protocol    => :http,
			:concurrency => 1
		}
		
		@owner_pipe = owner_pipe
		@options = options
		@previous_signal_handlers = {}
		@main_loop_generation  = 0
		@main_loop_thread_lock = Mutex.new
		@main_loop_thread_cond = ConditionVariable.new
		@threads = []
		@threads_mutex = Mutex.new
		@iterations         = 0
		@soft_termination_linger_time = 3
		@main_loop_running  = false
		
		#############
	end
	
	# Clean up temporary stuff created by the request handler.
	#
	# If the main loop was started by #main_loop, then this method may only
	# be called after the main loop has exited.
	#
	# If the main loop was started by #start_main_loop_thread, then this method
	# may be called at any time, and it will stop the main loop thread.
	def cleanup
		if @main_loop_thread
			@main_loop_thread_lock.synchronize do
				@graceful_termination_pipe[1].close rescue nil
			end
			@main_loop_thread.join
		end
		@server_sockets.each_value do |value|
			address, type, socket = value
			socket.close rescue nil
			if type == 'unix'
				File.unlink(address) rescue nil
			end
		end
		@owner_pipe.close rescue nil
	end
	
	# Check whether the main loop's currently running.
	def main_loop_running?
		@main_loop_thread_lock.synchronize do
			return @main_loop_running
		end
	end
	
	# Enter the request handler's main loop.
	def main_loop
		debug("Entering request handler main loop")
		reset_signal_handlers
		begin
			@graceful_termination_pipe = IO.pipe
			@graceful_termination_pipe[0].close_on_exec!
			@graceful_termination_pipe[1].close_on_exec!
			
			@main_loop_thread_lock.synchronize do
				@main_loop_generation += 1
				@main_loop_running = true
				@main_loop_thread_cond.broadcast
				
				@select_timeout = nil
				
				@selectable_sockets = []
				@server_sockets.each_value do |value|
					socket = value[2]
					@selectable_sockets << socket if socket
				end
				@selectable_sockets << @owner_pipe
				@selectable_sockets << @graceful_termination_pipe[0]
			end
			
			install_useful_signal_handlers
			start_threads
			wait_until_termination
			terminate_threads
			debug("Request handler main loop exited normally")

		rescue EOFError
			# Exit main loop.
			trace(2, "Request handler main loop interrupted by EOFError exception")
		rescue Interrupt
			# Exit main loop.
			trace(2, "Request handler main loop interrupted by Interrupt exception")
		rescue SignalException => signal
			trace(2, "Request handler main loop interrupted by SignalException")
			if signal.message != HARD_TERMINATION_SIGNAL &&
			   signal.message != SOFT_TERMINATION_SIGNAL
				raise
			end
		rescue Exception => e
			trace(2, "Request handler main loop interrupted by #{e.class} exception")
			raise
		ensure
			debug("Exiting request handler main loop")
			revert_signal_handlers
			@main_loop_thread_lock.synchronize do
				@graceful_termination_pipe[1].close rescue nil
				@graceful_termination_pipe[0].close rescue nil
				@selectable_sockets = []
				@main_loop_generation += 1
				@main_loop_running = false
				@main_loop_thread_cond.broadcast
			end
		end
	end
	
	# Start the main loop in a new thread. This thread will be stopped by #cleanup.
	def start_main_loop_thread
		current_generation = @main_loop_generation
		@main_loop_thread = Thread.new do
			begin
				main_loop
			rescue Exception => e
				print_exception(self.class, e)
			end
		end
		@main_loop_thread_lock.synchronize do
			while @main_loop_generation == current_generation
				@main_loop_thread_cond.wait(@main_loop_thread_lock)
			end
		end
	end
	
	# Remove this request handler from the application pool so that no
	# new connections will come in. Then make the main loop quit a few
	# seconds after the last time a connection came in. This all is to
	# ensure that no connections come in while we're shutting down.
	#
	# May only be called while the main loop is running. May be called
	# from any thread.
	def soft_shutdown
		@soft_termination_linger_thread ||= Thread.new do
			debug("Soft termination initiated")
			if @detach_key && @pool_account_username && @pool_account_password
				client = MessageClient.new(@pool_account_username, @pool_account_password)
				begin
					client.detach(@detach_key)
				ensure
					client.close
				end
			end
			wait_until_all_threads_are_idle
			debug("Soft terminating in #{@soft_termination_linger_time} seconds")
			sleep @soft_termination_linger_time
			@graceful_termination_pipe[1].close rescue nil
		end
	end

private
	def should_use_unix_sockets?
		# Historical note:
		# There seems to be a bug in MacOS X Leopard w.r.t. Unix server
		# sockets file descriptors that are passed to another process.
		# Usually Unix server sockets work fine, but when they're passed
		# to another process, then clients that connect to the socket
		# can incorrectly determine that the client socket is closed,
		# even though that's not actually the case. More specifically:
		# recv()/read() calls on these client sockets can return 0 even
		# when we know EOF is not reached.
		#
		# The ApplicationPool infrastructure used to connect to a backend
		# process's Unix socket in the helper server process, and then
		# pass the connection file descriptor to the web server, which
		# triggers this kernel bug. We used to work around this by using
		# TCP sockets instead of Unix sockets; TCP sockets can still fail
		# with this fake-EOF bug once in a while, but not nearly as often
		# as with Unix sockets.
		#
		# This problem no longer applies today. The web server now passes
		# all I/O through the HelperAgent, and the bug is no longer
		# triggered. Nevertheless, we keep this function intact so that
		# if something like this ever happens again, we know why, and we
		# can easily reactivate the workaround. Or maybe if we just need
		# TCP sockets for some other reason.
		
		#return RUBY_PLATFORM !~ /darwin/

		ruby_engine = defined?(RUBY_ENGINE) ? RUBY_ENGINE : "ruby"
		# Unix domain socket implementation on JRuby
		# is still bugged as of version 1.7.0. They can
		# cause unexplicable freezes when used in combination
		# with threading.
		return ruby_engine != "jruby"
	end

	def create_unix_socket_on_filesystem
		while true
			begin
				if defined?(NativeSupport)
					unix_path_max = NativeSupport::UNIX_PATH_MAX
				else
					unix_path_max = 100
				end
				socket_address = "#{passenger_tmpdir}/backends/ruby.#{generate_random_id(:base64)}"
				socket_address = socket_address.slice(0, unix_path_max - 10)
				socket = UNIXServer.new(socket_address)
				socket.listen(BACKLOG_SIZE)
				socket.close_on_exec!
				File.chmod(0600, socket_address)
				return ["unix:#{socket_address}", socket]
			rescue Errno::EADDRINUSE
				# Do nothing, try again with another name.
			end
		end
	end
	
	def create_tcp_socket
		# We use "127.0.0.1" as address in order to force
		# TCPv4 instead of TCPv6.
		socket = TCPServer.new('127.0.0.1', 0)
		socket.listen(BACKLOG_SIZE)
		socket.close_on_exec!
		socket_address = "tcp://127.0.0.1:#{socket.addr[1]}"
		return [socket_address, socket]
	end

	# Reset signal handlers to their default handler, and install some
	# special handlers for a few signals. The previous signal handlers
	# will be put back by calling revert_signal_handlers.
	def reset_signal_handlers
		Signal.list_trappable.each_key do |signal|
			begin
				prev_handler = trap(signal, DEFAULT)
				if prev_handler != DEFAULT
					@previous_signal_handlers[signal] = prev_handler
				end
			rescue ArgumentError
				# Signal cannot be trapped; ignore it.
			end
		end
		trap('HUP', IGNORE)
		PhusionPassenger.call_event(:after_installing_signal_handlers)
	end
	
	def install_useful_signal_handlers
		trappable_signals = Signal.list_trappable
		
		trap(SOFT_TERMINATION_SIGNAL) do
			begin
				soft_shutdown
			rescue => e
				print_exception("Passenger RequestHandler soft shutdown routine", e)
			end
		end if trappable_signals.has_key?(SOFT_TERMINATION_SIGNAL.sub(/^SIG/, ''))
		
		trap('ABRT') do
			print_status_report
		end if trappable_signals.has_key?('ABRT')
		trap('QUIT') do
			print_status_report
		end if trappable_signals.has_key?('QUIT')
	end
	
	def revert_signal_handlers
		@previous_signal_handlers.each_pair do |signal, handler|
			trap(signal, handler)
		end
	end

	def print_status_report
		warn(Utils.global_backtrace_report)
		warn("Threads: #{@threads.inspect}")
	end

	def start_threads
		common_options = {
			:app              => @app,
			:app_group_name   => @app_group_name,
			:connect_password => @connect_password,
			:analytics_logger => @analytics_logger
		}
		main_socket_options = common_options.merge(
			:server_socket => @main_socket,
			:socket_name => "main socket",
			:protocol => :session
		)
		http_socket_options = common_options.merge(
			:server_socket => @http_socket,
			:socket_name => "HTTP socket",
			:protocol => :http
		)

		# Used for marking threads that have finished initializing,
		# or failed during initialization. Threads that are not yet done
		# are not in `initialization_state`. Threads that have succeeded
		# set their own state to true. Threads that have failed set their
		# own state to false.
		initialization_state_mutex = Mutex.new
		initialization_state_cond = ConditionVariable.new
		initialization_state = {}

		# Actually start all the threads.
		thread_handler = @thread_handler
		expected_nthreads = 0

		@threads_mutex.synchronize do
			@concurrency.times do |i|
				thread = Thread.new(i) do |number|
					Thread.current.abort_on_exception = true
					begin
						Thread.current[:name] = "Worker #{number + 1}"
						handler = thread_handler.new(self, main_socket_options)
						handler.install
						initialization_state_mutex.synchronize do
							initialization_state[Thread.current] = true
							initialization_state_cond.signal
						end
						handler.main_loop
					ensure
						RobustInterruption.disable_interruptions do
							initialization_state_mutex.synchronize do
								initialization_state[Thread.current] = false
								initialization_state_cond.signal
							end
							unregister_current_thread
						end
					end
				end
				@threads << thread
				expected_nthreads += 1
			end

			thread = Thread.new do
				Thread.current.abort_on_exception = true
				begin
					Thread.current[:name] = "HTTP helper worker"
					handler = thread_handler.new(self, http_socket_options)
					initialization_state_mutex.synchronize do
						initialization_state[Thread.current] = true
						initialization_state_cond.signal
					end
					handler.install
					handler.main_loop
				ensure
					RobustInterruption.disable_interruptions do
						initialization_state_mutex.synchronize do
							initialization_state[Thread.current] = false
							initialization_state_cond.signal
						end
						unregister_current_thread
					end
				end
			end
			@threads << thread
			expected_nthreads += 1
		end

		# Wait until all threads have finished starting.
		initialization_state_mutex.synchronize do
			while initialization_state.size != expected_nthreads
				initialization_state_cond.wait(initialization_state_mutex)
			end
		end
	end

	def unregister_current_thread
		@threads_mutex.synchronize do
			@threads.delete(Thread.current)
		end
	end

	def wait_until_termination
		ruby_engine = defined?(RUBY_ENGINE) ? RUBY_ENGINE : "ruby"
		if ruby_engine == "jruby"
			# On JRuby, selecting on an input TTY always returns, so
			# we use threads to do the job.
			owner_pipe_watcher = IO.pipe
			owner_pipe_watcher_thread = Thread.new do
				Thread.current.abort_on_exception = true
				Thread.current[:name] = "Owner pipe waiter"
				begin
					@owner_pipe.read(1)
				ensure
					owner_pipe_watcher[1].write('x')
				end
			end
			begin
				ios = select([owner_pipe_watcher[0], @graceful_termination_pipe[0]])[0]
				if ios.include?(owner_pipe_watcher[0])
					trace(2, "Owner pipe closed")
				else
					trace(2, "Graceful termination pipe closed")
				end
			ensure
				owner_pipe_watcher_thread.kill
				owner_pipe_watcher_thread.join
				owner_pipe_watcher[0].close if !owner_pipe_watcher[0].closed?
				owner_pipe_watcher[1].close if !owner_pipe_watcher[1].closed?
			end
		else
			ios = select([@owner_pipe, @graceful_termination_pipe[0]])[0]
			if ios.include?(@owner_pipe)
				trace(2, "Owner pipe closed")
			else
				trace(2, "Graceful termination pipe closed")
			end
		end
	end

	def terminate_threads
		debug("Stopping all threads")
		done = false
		while !done
			@threads_mutex.synchronize do
				@threads.each do |thread|
					Utils::RobustInterruption.raise(thread)
				end
				done = @threads.empty?
			end
			sleep 0.02 if !done
		end
		debug("All threads stopped")
	end
	
	def wait_until_all_threads_are_idle
		debug("Waiting until all threads have become idle...")
		done = false
		while !done
			@threads_mutex.synchronize do
				done = @threads.all? do |thread|
					thread[:handler].idle?
				end
			end
			sleep 0.02 if !done
		end
		debug("All threads are now idle")
	end
end

end # module PhusionPassenger
