#  Phusion Passenger - http://www.modrails.com/
#  Copyright (C) 2010  Phusion
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; version 2 of the License.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

require 'phusion_passenger'
require 'phusion_passenger/abstract_installer'

namespace :package do
	@sources_dir = nil
	@verbosity = 0

	def sources_dir
		if !@sources_dir
			@sources_dir = `rpm -E '%{_sourcedir}'`.strip
		else
			@sources_dir
		end
	end

	def noisy_system(*args)
		puts args.join ' ' if @verbosity
		system(*args)
	end

	def create_tarball(verbosity = 0)
		working_dir = "/tmp/#{`whoami`.strip}-passenger-rpm-#{Process.pid}"
		sub_dir = "passenger-#{PhusionPassenger::VERSION_STRING}"
		FileUtils.rm_rf(working_dir, :verbose => verbosity > 0)
		begin
			FileUtils.mkdir_p("#{working_dir}/#{sub_dir}", :verbose => verbosity > 0)
			FileUtils.cp_r('.', "#{working_dir}/#{sub_dir}", :verbose => verbosity > 0)
			noisy_system('tar', "c#{verbosity >= 2 ? 'v' : ''}", "-C", working_dir, '-f', "#{sources_dir}/#{sub_dir}.tar.gz", sub_dir)
		ensure
			FileUtils.rm_rf("#{working_dir}", :verbose => verbosity > 0)
		end
	end

	def test_setup(*args)
			abort "Mock setup failed, see above for details" unless
				noisy_system('./rpm/release/mocksetup-first.sh', *args)
			NginxFetch.new.fetch(sources_dir)
	end

	desc "Package the current release into a set of RPMs"
	task 'rpm' => :rpm_verbosity do
		test_setup
		create_tarball(@verbosity)
		# Add a single -v for some feedback
		noisy_system(*(%w{./rpm/release/build.rb --single} + @build_verbosity))
	end

	desc "Build a Yum repository for the current release"
	task 'yum' => :rpm_verbosity do
		test_setup('--need-createrepo')
		create_tarball(@verbosity)
		# Add a single -v for some feedback
		noisy_system(*(%w{./rpm/release/build.rb --stage-dir=yum-repo --extra-packages=release/mock-repo} + @build_verbosity))
		Dir["yum-repo/{fedora,rhel}/*/{i386,x86_64}"].each do |dir|
			noisy_system('createrepo', dir)
		end
	end

	task 'rpm_verbosity' do
		if ENV['verbosity']
			if ENV['verbosity'] =~ /(true|yes|on)/i
				@verbosity = 1
			else
				@verbosity = ENV['verbosity'].to_i
				@build_verbosity = %w{-v} * (@verbosity == 0 ? 1 : @verbosity)
			end
		end
	end
end

class NginxFetch < PhusionPassenger::AbstractInstaller

	def fetch(dir)
		tarball = "nginx-#{PREFERRED_NGINX_VERSION}.tar.gz"
		return true if File.exists?("#{dir}/#{tarball}")
		download("http://sysoev.ru/nginx/#{tarball}", "#{dir}/#{tarball}")
	end
end