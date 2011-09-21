#!/usr/bin/env ruby

require 'net/ftp'

# ftp = Net::FTP.new('ftp://ftp.scientificlinux.org/linux/scientific/')
ftp = Net::FTP.new('ftp.scientificlinux.org')

ftp.passive = true
ftp.login
ftp.chdir('/linux/scientific')

%w{rhel epel}.each do |dir|
	if File.directory?(dir)
		puts "cd #{dir}"
		Dir.chdir(dir)
	end
end

%w{5 6}.each do |prefix|
	ftp.list("#{prefix}.*") do |line|
		file = line.gsub /.*\s+/, ''
		unless File.symlink?(file)
			puts "ln -s #{prefix} #{file}"
			File.symlink(prefix, file)
		end
	end
end
