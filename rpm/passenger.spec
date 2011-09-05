# RPM Spec file for Phusion Passenger
#
# The latest version of this file (as well as supporting files,
# documentation, and scripts to help build it) can be found here:
#
# http://github.com/erikogan/rubygem-passenger
#
# (If you fork this project feel free to add your repo below, but please
# do not remove the URL above.)

%define gemname passenger
%if %{?passenger_version:0}%{?!passenger_version:1}
  %define passenger_version 3.0.8
%endif
%if %{?passenger_release:0}%{?!passenger_release:1}
  %define passenger_release 2%{?dist}
%endif
%define passenger_epoch 1

%if %{?nginx_version:0}%{?!nginx_version:1}
  %define nginx_version 1.0.5
%endif

%define nginx_release %{passenger_version}_%{passenger_release}
%define nginx_user	passenger
%define nginx_group	%{nginx_user}
%define nginx_home      %{_localstatedir}/lib/nginx
%define nginx_home_tmp  %{nginx_home}/tmp
%define nginx_logdir    %{_localstatedir}/log/nginx
%define nginx_confdir   %{_sysconfdir}/nginx
%define nginx_datadir   %{_datadir}/nginx
%define nginx_webroot   %{nginx_datadir}/html

%define httpd_confdir	%{_sysconfdir}/httpd/conf.d

# Macros on the command-line overrides these defaults. You should also
# make sure these match the binaries found in your PATH. Also, if you
# change one, you'll probably want to change the others.
%{?!ruby: %define ruby /usr/bin/ruby}
%{?!rake: %define rake /usr/bin/rake}
%{?!gem:  %define gem  /usr/bin/gem}

# Debug packages are currently broken. So don't even build them
%define debug_package %nil

# Rather than requiring ruby (yum-builddep probably won't have it), set
# reasonable defaults to get us installed, then once ruby is installed via
# BuildRequires, it will use the correct values.
#
# There is SOME danger here if the values don't match and cause
# different BuildRequires to be visible. So DON'T DO THAT. :)
%define ruby_installed %(test -f %{ruby} && test -f %{gem} && echo 1 || echo 0)

%if %{ruby_installed}
  %define ruby_sitelib %(%{ruby} -rrbconfig -e "puts Config::CONFIG['sitelibdir']")
  %define ruby_version_patch %(%{ruby} -e 'puts "#{RUBY_VERSION}#{defined?(RUBY_PATCHLEVEL) ? %q{.} + RUBY_PATCHLEVEL.to_s : nil}"')
  # Does Gem::Version crash&burn on the version defined above? (RHEL5 might)
  %define broken_gem_version %(%{ruby} -rrubygems -e 'begin ; Gem::Version.create "%{passenger_version}" ; rescue => e ; puts 1 ; exit ; end ; puts 0')
  # %define gemdir %(%{ruby} -rubygems -e 'puts Gem::dir' 2>/dev/null)
  %define gemdir %(%{gem} env gemdir 2>/dev/null)
%else
  %define ruby_sitelib /usr/lib/ruby/site_ruby/1.8
  %define ruby_version_patch 1.8.7.352
  %define broken_gem_version 1
  %define gemdir /usr/lib/ruby/gems/1.8
%endif

%if %{broken_gem_version}
  # Strip any non-numeric version part
  %define gemversion %(echo '%{passenger_version}'|sed -e 's/\\.[^.]*[^.0-9]\\+[^.]*//g')
%else
  %define gemversion %{passenger_version}
%endif

# Invoke a shell to do a comparison, silly but it works across versions of RPM
%define gem_version_mismatch %([ '%{passenger_version}' != '%{gemversion}' ] && echo 1 || echo 0)

%define geminstdir %{gemdir}/gems/%{gemname}-%{gemversion}

%define perldir %(perl -MConfig -e 'print $Config{installvendorarch}')

# This will cause a chicken/egg problem where the dir isn't present yet
#% define gemnativedir % (%{ruby} -I%{_builddir}/%{gemname}-%{passenger_version}/lib -rphusion_passenger/platform_info/binary_compatibility -e 'puts PhusionPassenger::PlatformInfo.ruby_extension_binary_compatibility_ids.join("-")')
# %define native_libs_release %{passenger_release}_% (%{ruby} -I%{_builddir}/%{gemname}-%{passenger_version}/lib -rphusion_passenger/platform_info/binary_compatibility -e 'puts PhusionPassenger::PlatformInfo.ruby_extension_binary_compatibility_ids[0,2].join("_")')
%define native_libs_release %{passenger_release}_%{ruby_version_patch}

%{!?only_native_libs: %define only_native_libs 0}

%define is_fedora %{?fedora:1}%{?!fedora:0}
%define is_el6    %{?el6:1}%{?!el6:0}
# Apparently Amazon is an amalgam of EL5 & EL6. Super.
%define is_amzn   %{?amzn:1}%{?!amzn:0}
# There's no macro set for EL5, do it by elimination
%define is_el5    %{?!fedora:%{?!el6:%{?!amzn:1}}}%{?fedora:0}%{?el6:0}%{?amzn:0}

# It turns out Amazon Linux doesn't have libev afterall
%define has_libev %{?fedora:1}%{?el6:1}%{?!fedora:%{?!el6:0}}

# They DID standardize, now just legacy support:
%define sharedir %{?is_el5:%{_datadir}}%{?!is_el5:%{_datarootdir}}

Summary: Easy and robust Ruby web application deployment
Name: rubygem-%{gemname}
Version: %{passenger_version}
Release: %{passenger_release}
Group: System Environment/Daemons
License: Modified BSD
URL: http://www.modrails.com/
Source0: %{gemname}-%{passenger_version}.tar.gz
Source1: nginx-%{nginx_version}.tar.gz
Source100: apache-passenger.conf.in
Source101: nginx-passenger.conf.in
Source200: rubygem-passenger.te
Source201: rubygem-passenger.fc.in
Source202: rubygem-passenger.if
# The most recent nginx RPM no longer includes this plugin. Remove it from the
# SRPM
# # Ignore everything after the ?, it's meant to trick rpmbuild into
# # finding the correct file
# Source300: http://github.com/gnosek/nginx-upstream-fair/tarball/master?/nginx-upstream-fair.tar.gz
Patch0: passenger-force-native.patch
Patch1: passenger-prevent-dot-cleanup.patch
Patch2: passenger-standalone-nginx-no-unused-but-set-variable.patch
Patch3: passenger-standalone-progress-crash-fix.patch
Patch4: passenger-no-asciidoc-html5.patch
Patch5: passenger-selinux-aware-helper-agents.patch
Patch6: passenger-el5-selinux-lacks-open-on-file.patch
BuildRoot: %{_tmppath}/%{name}-%{passenger_version}-%{passenger_release}-root-%(%{__id_u} -n)
Requires: rubygems
Requires: rubygem(rake) >= 0.8.1
Requires: rubygem(fastthread) >= 1.0.1
Requires: rubygem(daemon_controller) >= 0.2.5
Requires: rubygem(rack)
BuildRequires: ruby-devel
BuildRequires: gcc-c++
%if !%{only_native_libs}
BuildRequires: httpd-devel
BuildRequires: rubygems
BuildRequires: rubygem(rake) >= 0.8.1
BuildRequires: rubygem(rack)
BuildRequires: rubygem(fastthread) >= 1.0.1
BuildRequires: pcre-devel
%if !%{is_el5}
BuildRequires: perl-ExtUtils-Embed
BuildRequires: libcurl-devel
%if %{is_fedora}
BuildRequires: source-highlight
%endif
%else
BuildRequires: curl-devel
%endif
BuildRequires: doxygen
BuildRequires: asciidoc
BuildRequires: graphviz
# standaline build deps
%if %{has_libev}
BuildRequires: libev-devel
%endif
BuildRequires: rubygem(daemon_controller) >= 0.2.5
# native build deps
BuildRequires: libselinux-devel
%if !%{is_el5}
BuildRequires: selinux-policy
%else
BuildRequires: selinux-policy-devel
%endif
# nginx build deps
BuildRequires: pcre-devel
BuildRequires: zlib-devel
BuildRequires: openssl-devel
%if !%{is_el5}
BuildRequires: perl-devel
%else
BuildRequires: perl
%endif
BuildRequires: perl(ExtUtils::Embed)
BuildRequires: libxslt-devel
BuildRequires: GeoIP-devel
BuildRequires: gd-devel
%endif # only_native_libs
# Can't have a noarch package with an arch'd subpackage
#BuildArch: noarch
Provides: rubygem(%{gemname}) = %{passenger_version}
Epoch: %{passenger_epoch}

%description
Phusion Passenger™ — a.k.a. mod_rails or mod_rack — makes deployment
of Ruby web applications, such as those built on the revolutionary
Ruby on Rails web framework, a breeze. It follows the usual Ruby on
Rails conventions, such as “Don’t-Repeat-Yourself”.

%if %{gem_version_mismatch}
**NOTE: Because the default Gem::Version doesn't accept the correct
version, it is installed as %{gemversion} instead of %{passenger_version}.
%endif

%if !%{only_native_libs}

%package native
Summary: Phusion Passenger native extensions
Group: System Environment/Daemons
Requires: %{name} = %{passenger_epoch}:%{passenger_version}-%{passenger_release}
%if %{has_libev}
Requires: libev
%endif
Requires(post): policycoreutils, initscripts
Requires(preun): policycoreutils, initscripts
Requires(postun): policycoreutils
Epoch: %{passenger_epoch}
%description native
Phusion Passenger™ — a.k.a. mod_rails or mod_rack — makes deployment
of Ruby web applications, such as those built on the revolutionary
Ruby on Rails web framework, a breeze. It follows the usual Ruby on
Rails conventions, such as “Don’t-Repeat-Yourself”.

This package contains the native code extensions for Apache & Nginx bindings

%endif #! only_native_libs

%package native-libs
Summary: Phusion Passenger native extensions
Group: System Environment/Daemons
Release: %{native_libs_release}
Epoch: %{passenger_epoch}
Requires: %{name}-native = %{passenger_epoch}:%{passenger_version}-%{passenger_release}
Requires: ruby = %{ruby_version_patch}
Provides: rubygem-passenger-native-libs = %{passenger_epoch}:%{passenger_version}-%{passenger_release}
%description native-libs
Phusion Passenger™ — a.k.a. mod_rails or mod_rack — makes deployment
of Ruby web applications, such as those built on the revolutionary
Ruby on Rails web framework, a breeze. It follows the usual Ruby on
Rails conventions, such as “Don’t-Repeat-Yourself”.

This package contains the native shared library for Apache & Nginx
bindings, built against ruby sources. It has been separated so that
installing a new ruby interpreter only necessitates rebuilding this
package.

%if !%{only_native_libs}

%package -n passenger-standalone
Summary: Standalone Phusion Passenger Server
Group: System Environment/Daemons
Requires: %{name} = %{passenger_epoch}:%{passenger_version}-%{passenger_release}
Requires: %{name}-native-libs = %{passenger_epoch}:%{passenger_version}-%{passenger_release}
%if %{has_libev}
Requires: libev
%endif
Requires: libselinux
Epoch: %{passenger_epoch}
Obsoletes: rubygem-passenger-standalone
Provides: rubygem-passenger-standalone
%description -n passenger-standalone
Phusion Passenger™ — a.k.a. mod_rails or mod_rack — makes deployment
of Ruby web applications, such as those built on the revolutionary
Ruby on Rails web framework, a breeze. It follows the usual Ruby on
Rails conventions, such as “Don’t-Repeat-Yourself”.

This package contains the standalone Passenger server

%package -n mod_passenger
Summary: Apache Module for Phusion Passenger
Group: System Environment/Daemons
Requires: %{name}-native-libs = %{passenger_epoch}:%{passenger_version}-%{passenger_release}
Requires: libselinux
Requires: httpd
#BuildArch: %_target_arch
Obsoletes: rubygem-passenger-apache
Epoch: %{passenger_epoch}
%description -n mod_passenger
Phusion Passenger™ — a.k.a. mod_rails or mod_rack — makes deployment
of Ruby web applications, such as those built on the revolutionary
Ruby on Rails web framework, a breeze. It follows the usual Ruby on
Rails conventions, such as “Don’t-Repeat-Yourself”.

This package contains the pluggable Apache server module for Passenger.

%package -n nginx-passenger
Summary: nginx server with Phusion Passenger enabled
Group: System Environment/Daemons
Requires: %{name} = %{passenger_epoch}:%{passenger_version}
Version: %{nginx_version}
Release: %{passenger_version}_%{passenger_release}
Requires: %{name}-native-libs = %{passenger_epoch}:%{passenger_version}-%{passenger_release}
Requires: pcre
Requires: zlib
Requires: openssl
Requires: perl(:MODULE_COMPAT_%(eval "`%{__perl} -V:version`"; echo $version))
Requires: GeoIP
Requires: gd
Requires: nginx-alternatives
Requires: libselinux
Epoch: %{passenger_epoch}
%description -n nginx-passenger
Phusion Passenger™ — a.k.a. mod_rails or mod_rack — makes deployment
of Ruby web applications, such as those built on the revolutionary
Ruby on Rails web framework, a breeze. It follows the usual Ruby on
Rails conventions, such as “Don’t-Repeat-Yourself”.

This package includes an nginx server with Passenger compiled in.

%endif # !only_native_libs

%define perlfileckinner $SIG{__WARN__} = sub {die @_};
%define perlfileck BEGIN { %perlfileckinner } ;
%define perlfileescd %(echo '%{perlfileck}' | sed -e 's/[$@]/\\\\&/g')

%prep
%setup -q -n %{gemname}-%{passenger_version} -b 1
# %setup -q -T -D -n nginx-%{nginx_version} -a 300
# # Fix the CWD
# %setup -q -T -D -n %{gemname}-%{passenger_version}
%patch0 -p1

# FC14 doesn't like the Doxygen MD5, and regenerates the files, removing
# the *.dot files in the process. Prevent that removal
# %patch1 -p1

%if %{?fc15:1}%{?!fc15:0}
# Nginx doesn't compile with -Wall on FC15, add an argument to the
# Passenger Standalone build to ignore the fatal warning
%patch2 -p1
%endif

# Passenger standalone progress notification crashes consistently when
# built in mock, yet not outside of it. Very strange. Stranger, I got my
# first crash outside of mock.
%patch3 -p1

# They're using a newer version of asciidoc than is currently available,
# even on FC15. This should be revisited for FC16
%patch4 -p1

# Make HelperAgent transition back to httpd_t on the ruby exec
%patch5 -p1

# FC14 doesn't like the new doxygen sources at all, removing them to
# regenerate all of it, per Hong Li's recommendation
rm -rf doc/cxxapi

# Rather than hard-coding the path into the patch, change it here so
# that it's consistent with the %{ruby} macro, which might be defined on
# the command-line (4 %'s = 2)
perl -pi -e '%{perlfileck} s{%%%%GEM_INSTALL_DIR%%%%}{%{geminstdir}};s{%%%%APACHE_INSTALLED_MOD%%%%}{%{_libdir}/httpd/modules/mod_passenger.so}' lib/phusion_passenger.rb ext/common/ResourceLocator.h

%if %{gem_version_mismatch}
  %{warn:
***
*** WARNING: Your Gem::Version crashes on '%{passenger_version},'
***          Falling back to use '%gemversion' internally
***

}
  # Use sed rather than a patch, so it's more resilliant to version changes
  sed -i -e "s/\(^[ \t]VERSION_STRING *= *'[0-9]\+\.[0-9]\+\.[0-9]\+\)[^']\+/\1/" lib/phusion_passenger.rb
  sed -i -e 's/^\(#define PASSENGER_VERSION "[0-9]\+\.[0-9]\+\.[0-9]\+\)[^"]\+/\1/' ext/common/Constants.h
%endif

# Fix the preferred version
perl -pi -e "s{(PREFERRED_NGINX_VERSION\s*=\s*(['\"]))[\d\.]+\2}{\${1}%{nginx_version}\$2}" lib/phusion_passenger.rb

# RPM finds these in shebangs and assumes they're requirements. Clean them up here rather than in the install-dir.
find test -type f -print0 | xargs -0 perl -pi -e '%{perlfileck} s{#!(/opt/ruby.*|/usr/bin/ruby1.8)}{%{ruby}}g'


%build
%if %{has_libev}
export USE_VENDORED_LIBEV=false
# This isn't honored
# export CFLAGS='%optflags -I/usr/include/libev'
export LIBEV_CFLAGS='-I/usr/include/libev'
export LIBEV_LIBS='-lev'
%endif

%if %is_el6
%ifarch x86_64
# x86_64 EL6 build started crashing when source-highlight was not
# present. That is probably the CORRECT behavior. But it's inconsistent
# & inconvenient.
mkdir new_path
export PATH=$PATH:$PWD/new_path
cat <<EOF > new_path/source-highlight
#!/bin/sh
echo "source-highlight not installed!" >&2
exit 0
EOF
chmod +x new_path/source-highlight
%endif
%endif

%if %{only_native_libs}
   %{rake} native_support
%else
  %{rake} package
  %{rake} apache2
  %{rake} nginx

  ### SELINUX
  rm -rf selinux
  mkdir selinux
  cd selinux
  cp %{SOURCE200} %{SOURCE202} .
  perl -pe 's{%%GEMDIR%%}{%geminstdir}g;s{%%VAR%%}{%_var}g' %{SOURCE201} > rubygem-passenger.fc
  %if %is_el5
    %patch6
  %endif
  make -f %{sharedir}/selinux/devel/Makefile
  cd ..

  ### NGINX
  cd ../nginx-%{nginx_version}

  #export FAIRDIR=%{_builddir}/nginx-%{nginx_version}/gnosek-nginx-upstream-fair-*
  # I'm not sure why this fails on RHEL but not Fedora. I guess GCC 4.4 is
  # smarter about it than 4.1? It feels wrong to do this, but I don't see
  # an easier way out.
  %if !%{is_el5}
    %define nginx_ccopt %{optflags} %{?fc15:-Wno-unused-but-set-variable}
  %else
    %define nginx_ccopt %(echo "%{optflags}" | sed -e 's/SOURCE=2/& -Wno-unused/')
  %endif

  ### Stolen [and hacked] from the nginx spec file
  export DESTDIR=%{buildroot}
  ./configure \
    --user=%{nginx_user} \
    --group=%{nginx_group} \
    --prefix=%{nginx_datadir} \
    --sbin-path=%{_sbindir}/nginx.passenger \
    --conf-path=%{nginx_confdir}/nginx.conf \
    --error-log-path=%{nginx_logdir}/error.log \
    --http-log-path=%{nginx_logdir}/access.log \
    --http-client-body-temp-path=%{nginx_home_tmp}/client_body \
    --http-proxy-temp-path=%{nginx_home_tmp}/proxy \
    --http-fastcgi-temp-path=%{nginx_home_tmp}/fastcgi \
    --http-uwsgi-temp-path=%{nginx_home_tmp}/uwsgi \
    --http-scgi-temp-path=%{nginx_home_tmp}/scgi \
    --pid-path=%{_localstatedir}/run/nginx.pid \
    --lock-path=%{_localstatedir}/lock/subsys/nginx \
    --with-http_ssl_module \
    --with-http_realip_module \
    --with-http_addition_module \
    --with-http_xslt_module \
    --with-http_image_filter_module \
    --with-http_geoip_module \
    --with-http_sub_module \
    --with-http_dav_module \
    --with-http_flv_module \
    --with-http_gzip_static_module \
    --with-http_random_index_module \
    --with-http_secure_link_module \
    --with-http_degradation_module \
    --with-http_stub_status_module \
    --with-http_perl_module \
    --with-mail \
    --with-file-aio \
    --with-mail_ssl_module \
    --with-ipv6 \
    --add-module="$RPM_BUILD_DIR/passenger-%{passenger_version}/ext/nginx" \
    --with-cc-opt="%{nginx_ccopt} $(pcre-config --cflags)" \
    --with-ld-opt="-Wl,-E" # so the perl module finds its symbols

  # THIS is ugly (yet now greatly simplified). It corrects the
  # check-buildroot error on the string saved for 'nginx -V'
  #
  # In any case, fix it correctly later
  perl -pi -e '%{perlfileck} s<%{buildroot}><>g;s<%{_builddir}><%%{_builddir}>g;' objs/ngx_auto_config.h

  # Also do it for passenger-standalone (and I thought the above was ugly)
  perl -pi.nohack -0777 -e 's!(^\s*run_command_with_throbber.*"Preparing Nginx...".*\n(\s*))(yield.*?\n)!${2}\@\@hack_success = false\n$1yield_result = $3${2}abort "nginx-hack failed" unless \@\@hack_success || system(*(%w{perl -pi -e} + ["%{perlfileescd} s<%{buildroot}><>g;s<%{_builddir}><%%{_builddir}>g;", "objs/ngx_auto_config.h"]))\n${2}\# Why is this running many times?\n${2}\@\@hack_success = true\n${2}yield_result\n!im' %{_builddir}/passenger-%{passenger_version}/lib/phusion_passenger/standalone/runtime_installer.rb

  make %{?_smp_mflags}

  cd -
%endif # !only_native_libs

%install
%if %{has_libev}
export USE_VENDORED_LIBEV=false
# This isn't honored
# export CFLAGS='%optflags -I/usr/include/libev'
export LIBEV_CFLAGS='-I/usr/include/libev'
export LIBEV_LIBS='-lev'
%endif

rm -rf %{buildroot}
mkdir -p %{buildroot}%{gemdir}

%if !%{only_native_libs}
%{gem} install --local --install-dir %{buildroot}%{gemdir} \
               --force --rdoc pkg/%{gemname}-%{gemversion}.gem
mkdir -p %{buildroot}/%{_bindir}
mv %{buildroot}%{gemdir}/bin/* %{buildroot}/%{_bindir}
rmdir %{buildroot}%{gemdir}/bin
# Nothing there
# find %{buildroot}%{geminstdir}/bin -type f | xargs chmod a+x

mkdir -p %{buildroot}/%{_libdir}/httpd/modules
install -m 0644 ext/apache2/mod_passenger.so %{buildroot}/%{_libdir}/httpd/modules

mkdir -p %{buildroot}/%{nginx_datadir}
mkdir -p %{buildroot}/%{nginx_datadir}
mkdir -p %{buildroot}/%{nginx_confdir}
mkdir -p %{buildroot}/%{nginx_logdir}
mkdir -p %{buildroot}/%{httpd_confdir}
mkdir -p %{buildroot}/%{_var}/log/passenger-analytics

# For some reason FC15's rpm isn't interpreting the %ghost directive. 
# This will probably lead to trouble, but it won't build without it.
# (EL5 has it, too)
%if %{?fc15:1}%{?!fc15:%{is_el5}}
mkdir -p %{buildroot}/%{_var}/run/passenger
%endif

# I should probably figure out how to get these into the gem
cp -ra agents %{buildroot}/%{geminstdir}

# PASSENGER STANDALONE (this is going to recompile nginx)
%{ruby} ./bin/passenger package-runtime --nginx-version %{nginx_version} --nginx-tarball %{SOURCE1} %{buildroot}/%{_var}/lib/passenger-standalone
# Now unpack the tarballs it just created
# It's 2am, revisit this insanity in the light of morning
standalone_dir=$(bash -c 'ls -d $1 | tail -1' -- %{buildroot}/%{_var}/lib/passenger-standalone/%{passenger_version}-*)
native_dir=%{buildroot}/%{_var}/lib/passenger-standalone/natively-packaged

mkdir -p $standalone_dir/support
mkdir -p $standalone_dir/nginx-%{nginx_version}
tar -zx -C $standalone_dir/nginx-%{nginx_version} -f $standalone_dir/nginx-%{nginx_version}.tar.gz
tar -zx -C $standalone_dir/support -f $standalone_dir/support.tar.gz

# Hong Li says the binaries are relocatable, so we don't have to jump
# through hoops to change directories. Just move it.
mv $standalone_dir $native_dir
mv $native_dir/support/ext/ruby/*-linux $native_dir/support/ext/ruby/native

# Unhack
mv lib/phusion_passenger/standalone/runtime_installer.rb.nohack lib/phusion_passenger/standalone/runtime_installer.rb
install -m 0644 lib/phusion_passenger/standalone/runtime_installer.rb $native_dir/support/lib/phusion_passenger/standalone/runtime_installer.rb

# SELINUX
install -p -m 644 -D selinux/%{name}.pp %{buildroot}%{sharedir}/selinux/packages/%{name}/%{name}.pp

# NGINX
cd ../nginx-%{nginx_version}
make install DESTDIR=%{buildroot} INSTALLDIRS=vendor
cd -

%endif #!only_native_libs

##### NATIVE LIBS INSTALL
mkdir -p %{buildroot}/%{geminstdir}/ext/ruby/native
cp -ra ext/ruby/*-linux/* %{buildroot}/%{geminstdir}/ext/ruby/native

%if !%{only_native_libs}
#### Clean up everything we don't care about
rm -rf %{buildroot}/usr/share/nginx %{buildroot}/%{nginx_confdir}
# # Assume the old version is good enough. Probably not wise.
# rm -rf %{buildroot}%{perldir} %{buildroot}%{_mandir}/man3/nginx.3pm*
rm -f %{buildroot}%{perldir}/{auto/nginx/.packlist,perllocal.pod}
# RHEL distinguishes these dirs
rm -f %{buildroot}%(perl -MConfig -e 'print $Config{installarchlib}')/perllocal.pod
mv %{buildroot}%{perldir}/auto/nginx/nginx{,_passenger}.bs
mv %{buildroot}%{perldir}/auto/nginx/nginx{,_passenger}.so
mv %{buildroot}%{perldir}/nginx{,_passenger}.pm
mv %{buildroot}%{_mandir}/man3/nginx.3pm{,_passenger}

install -p -d -m 0755 %{buildroot}/%{nginx_confdir}/conf.d
#install -m 0644 %{SOURCE100} %{buildroot}/%{httpd_confdir}/passenger.conf
#install -m 0644 %{SOURCE101} %{buildroot}/%{nginx_confdir}/conf.d/passenger.conf
perl -pe 's{%%ROOT}{%geminstdir}g;s{%%RUBY}{%ruby}g' %{SOURCE100} > %{buildroot}/%{httpd_confdir}/passenger.conf
perl -pe 's{%%ROOT}{%geminstdir}g;s{%%RUBY}{%ruby}g' %{SOURCE101} > %{buildroot}/%{nginx_confdir}/conf.d/passenger.conf

# CLEANUP
rm -f $native_dir/support/ext/ruby/native/mkmf.log
# Reversed logic from most other tests
%if %{?fedora:0}%{?!fedora:1}
rm -f $native_dir/support/ext/libev/config.log
%endif

# REMOVE THIS TO FORCE 'native-packaged' (it's still in doc)
rm %{buildroot}/%{geminstdir}/DEVELOPERS.TXT

# This is still needed
%if %{has_libev}
  %define libevmunge %nil
%else
  %define libevmunge $native_dir/support/ext/libev/config.status $native_dir/support/ext/libev/Makefile
%endif

perl -pi -e '%perlfileck s{%buildroot}{}g;s<%{_builddir}><%%{_builddir}>g' \
	$native_dir/support/ext/ruby/native/Makefile %{libevmunge}

%define base_files base-package-files

### BUILD FILE LIST (To remove files from the base package that will be installed by subpackages)
cat <<EOF > %{base_files}
%defattr(-, root, root, -)
%doc %{gemdir}/doc/%{gemname}-%{gemversion}
%doc README
%doc DEVELOPERS.TXT
%{_bindir}/passenger-install-apache2-module
%{_bindir}/passenger-install-nginx-module
%{_bindir}/passenger-config
%{_bindir}/passenger-status
%{_bindir}/passenger-memory-stats
%{_bindir}/passenger-make-enterprisey
%{gemdir}/cache/%{gemname}-%{gemversion}.gem
%{gemdir}/specifications/%{gemname}-%{gemversion}.gemspec
EOF

# This feels wrong (reordering arch & os) but if it helps....
# ...Going one step further and also stripping all the installed *.o files
# Move the file find here to catch the byte-compiled Python files
%define __spec_install_post \
    %{?__debug_package:%{__debug_install_post}} \
    %{__os_install_post} \
    find $native_dir -name \*.o -o -name \*.so | xargs strip ; \
    find %{buildroot}/%{geminstdir} \\( -type d \\( -name native -o -name agents \\) \\) -prune -o \\( -type f -print \\) | perl -pe 's{^%{buildroot}}{};s{^//}{/};s/([?|*'\\''\"])/\\\\$1/g;s{(^|\\n$)}{\"$&}g' >> %{base_files} \
    %{__arch_install_post}

%post -n mod_passenger
if [ $1 == 1 ]; then
  fixfiles -R mod_passenger restore
fi

%post -n nginx-passenger
if [ $1 == 1 ]; then
  /usr/sbin/alternatives --install /usr/sbin/nginx nginx \
				   /usr/sbin/nginx.passenger 50 \
    --slave %{perldir}/auto/nginx/nginx.so nginx.so \
	    %{perldir}/auto/nginx/nginx_passenger.so \
    --slave %{perldir}/auto/nginx/nginx.bs nginx.bs \
	    %{perldir}/auto/nginx/nginx_passenger.bs \
    --slave %{perldir}/nginx.pm nginx.pm %{perldir}/nginx_passenger.pm \
    --slave %{_mandir}/man3/nginx.3pm.gz nginx.man \
	    %{_mandir}/man3/nginx_passenger.3pm.gz
  fixfiles -R nginx-passenger restore
  # It appears that the EPEL nginx package has no SELinux configuration, use our policy for now
  fixfiles -R nginx restore 
fi

%postun -n nginx-passenger
if [ $1 == 0 ]; then # final removal
  /usr/sbin/alternatives --remove nginx /usr/sbin/nginx.passenger
fi

%post native
# Always install the module, otherwise upgrades will have the old version
# if [ "$1" -le "1" ] ; then # First install
# semodule -i %{sharedir}/selinux/packages/%{name}/%{name}.pp 2>/dev/null || :
# fi
semodule -i %{sharedir}/selinux/packages/%{name}/%{name}.pp 2>/dev/null || :
fixfiles -R %{name} restore
fixfiles -R %{name}-native restore

%preun native
if [ "$1" -lt "1" ] ; then # Final removal
  semodule -r rubygem_%{gemname} 2>/dev/null || :
else
  fixfiles -R %{name} restore
  fixfiles -R %{name}-native restore
fi

%postun native
# This doesn't seem to be running
if [ "$1" -ge "1" ] ; then # Upgrade
semodule -i %{sharedir}/selinux/packages/%{name}/%{name}.pp 2>/dev/null || :
fi
%endif # !only_native_libs


%clean
rm -rf %{buildroot}

%if !%{only_native_libs}
%files -f %{base_files}

%files native
%{geminstdir}/agents/PassengerLoggingAgent
%{geminstdir}/agents/PassengerWatchdog
%{sharedir}/selinux/packages/%{name}/%{name}.pp
%{_var}/log/passenger-analytics
%ghost %dir %{_var}/run/passenger

%files -n passenger-standalone
%doc doc/Users\ guide\ Standalone.html
%doc doc/Users\ guide\ Standalone.txt
%{_bindir}/passenger
%{_var}/lib/passenger-standalone/natively-packaged/
%attr(755, root, root) %{_var}/lib/passenger-standalone/natively-packaged/support/helper-scripts/*

%files -n mod_passenger
%doc doc/Users\ guide\ Apache.html
%doc doc/Users\ guide\ Apache.txt
%{_libdir}/httpd/modules/mod_passenger.so
%{geminstdir}/agents/apache2
%config %{httpd_confdir}/passenger.conf

%files -n nginx-passenger
%doc doc/Users\ guide\ Nginx.html
%doc doc/Users\ guide\ Nginx.txt
%config %{nginx_confdir}/conf.d/passenger.conf
/usr/sbin/nginx.passenger
%{geminstdir}/agents/nginx
%{perldir}/auto/nginx/nginx*
%{perldir}/nginx*
%{_mandir}/man3/nginx*
%endif # !only_native_libs

%files native-libs
# %{geminstdir}/ext/ruby/%{gemnativedir}
%{geminstdir}/ext/ruby/native


%changelog
* Fri Aug 12 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.8-2
- Fix the libev dependency for EL6

* Wed Aug  3 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.8-1
- Bump version to 3.0.8
- Bump nginx to 1.0.5

* Sun Jul 31 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.7-5
- Fix segfault when SELinux is disabled
- Fix mod_passenger's native-libs dependency
- Add httpd to the list of mod_passenger dependencies

* Thu Jul  7 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.7-4
- Move PassengerHelperAgent to its own SELinux domain
- Bump nginx to 1.0.2
- Add support for FC15
- Add support for RHEL6
- Fix passenger-standalone dependencies and script permissions

* Sun Apr 17 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.7-3
- Remove file-tail from BuildRequire as well

* Thu Apr 14 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.7-2
- Add SELinux permissions for ps (and a boolean to turn it off: httpd_use_ps)

* Thu Apr 14 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.7-1
- Bump version to 3.0.7
- Bump nginx version 1.0.0

* Mon Apr  4 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.6-2
- Removing requirement on file-tail

* Sun Apr  3 2011 Erik Ogan <erik@steathymonkeys.com> - 1:3.0.6-1
- Bump to 3.0.6

* Fri Mar 11 2011 Erik Ogan <erik@stealthymonkeys.com> - 1:3.0.5-1
- Bump to 3.0.5

* Wed Mar  2 2011 Erik Ogan <erik@stealthymonkeys.com> - 1:3.0.4-1
- Bump to 3.0.4

* Fri Feb 25 2011 Erik Ogan <erik@stealthymonkeys.com> - 1:3.0.3-1
- Bump to 3.0.3

* Sat Feb  5 2011 Erik Ogan <erik@stealthymonkeys.com> - 3.0.2-2
- Bump nginx to 0.8.54
- Fix nginx-passenger to include passenger (somehow this got lost in the
  shuffle, yet tests continued to pass. Testing updated as well)
- Move agents/apache2 & agents/nginx into their respective packages
- Fix BuildRequires when only_native_libs is defined

* Thu Dec 16 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.2-1
- Bump to 3.0.2

* Mon Dec 13 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.1-4
- rename rubygem-passenger-standalone to passenger-standalone
- Add graphviz to the build requirements (for /usr/bin/dot)

* Thu Dec  2 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.1-3
- Stop double-packaging files from -native & -native-libs in the base package

* Tue Nov 30 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.1-2
- Remove (most of) the kludges to remove %%{builddir} from installed files.
- Blessed natively-packaged patch from Hong Li
- Migration to the more static directory structure

* Mon Nov 29 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.1-1
- Integration into passenger source
- Bump to 3.0.1

* Mon Nov 15 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-11
- Fix passenger-standalone

* Fri Nov 12 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-10
- Bump nginx to version 0.8.53 and build it by hand based on the newer
  nginx specfile

* Sun Nov  7 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-9
- Add passenger-analytics directory, so the server doesn't try to create
  it. (SELinux violation)

* Sun Oct 31 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-8
- Fix embedded Perl module

* Fri Oct 29 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-7
- Add back all the missing directives from nginx.spec (Perl is
  untested and may be broken)

* Fri Oct 29 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-6
- Add upstream-fair load-balancer back to nginx
- Add the original CFLAGS back to nginx (with -Wno-unused kludge for RHEL5)

* Sat Oct 23 2010 Erik Ogan <erik@cloudshield.com> - 3.0.0-5
- RHEL/CentOS Ruby is too old to support RUBY_PATCHLEVEL

* Sat Oct 23 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-4
- --define 'only_native_libs 1' to rebuild native_support.so for a
  different ruby engine.
- make sure native-libs release includes passenger release and ruby patch level
- remove the macros that rely on %%{_builddir} already being unpacked

* Fri Oct 22 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-3
- Break the passenger_native_support.so into its own package

* Thu Oct 21 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-2
- rename rubygem-passenger-apache => mod_passenger

* Thu Oct 21 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0-1
- Version bump to 3.0.0

* Wed Oct 18 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0.pre4-2
- use nginx-alternatives

* Sun Oct 17 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0.pre4-1
- Nginx suport

* Mon Oct 11 2010 Erik Ogan <erik@stealthymonkeys.com> - 3.0.0.pre4-0
- Test for Gem::Version issues with the version and work around it.
- Initial Spec File
