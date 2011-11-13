Summary: Phusion Passenger release RPM/Yum repository configuration
Name: passenger-release
Version: 3
Release: 6%{?dist}
License: MIT
Group: Group: System Environment/Base
URL: http://passenger.stealthymonkeys.com/
Source0: mirrors-passenger
Source1: RPM-GPG-KEY-stealthymonkeys
Source2: RPM-GPG-KEY-stealthymonkeys.rhel5
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root
BuildArch: noarch

%description
Phusion Passenger Yum/RPM configuration. This package contains the Yum
repository configuration to install & update Phusion Passenger, as
well as the GPG signing key to verify them.

%prep
#%setup -c

%if %{?el5:1}%{?!el5:0}
%define key_suffix .rhel5
%else
%define key_suffix %nil
%endif

%{?el5:name='Red Hat Enterprise' version='5' path='rhel'}
%{?el6:name='Red Hat Enterprise' version='6' path='rhel'}

%{?fc13:name='Fedora Core' version='13' path='fedora'}
%{?fc14:name='Fedora Core' version='14' path='fedora'}
%{?fc15:name='Fedora Core' version='15' path='fedora'}
%{?fc16:name='Fedora Core' version='16' path='fedora'}

if [ -z "$name" ] ; then
 echo "Please specify a distro to build for (f'rex: el5 or fc16)" >&2
 exit 255
fi

%{__cat} <<EOF > passenger.repo
### Name: Phusion Passenger RPM Repository for $name $version
### URL: %{url}
[passenger]
name = $name \$releasever - Phusion Passenger
baseurl = %{url}$path/\$releasever/\$basearch
mirrorlist = %{url}$path/mirrors
#mirrorlist = file:///etc/yum.repos.d/mirrors-passenger
enabled = 1
gpgkey = file:///etc/pki/rpm-gpg/RPM-GPG-KEY-passenger%{key_suffix}
gpgcheck = 1

### Name: Phusion Passenger RPM Repository for $name $version (TESTING)
### URL: %{url}
[passenger-testing]
name = $name \$releasever - Phusion Passenger - TEST
baseurl = %{url}$path/\$releasever/\$basearch/testing/
enabled = 0
gpgkey = file:///etc/pki/rpm-gpg/RPM-GPG-KEY-passenger%{key_suffix}
gpgcheck = 0
EOF

for mirror in $(%{__cat} %{SOURCE0}); do
  echo "$mirror/$path/\$releasever/\$ARCH/"
done > mirrors-passenger

%build

%install
rm -rf %{buildroot}
%{__install} -D -p -m 0644 %{SOURCE1}%{key_suffix} %{buildroot}%{_sysconfdir}/pki/rpm-gpg/RPM-GPG-KEY-passenger%{key_suffix}
%{__install} -D -p -m 0644 passenger.repo %{buildroot}%{_sysconfdir}/yum.repos.d/passenger.repo



%clean
rm -rf %{buildroot}


%files
%defattr(-,root,root,-)
%doc mirrors-passenger
%{_sysconfdir}/pki/rpm-gpg/RPM-GPG-KEY-passenger%{key_suffix}
%{_sysconfdir}/yum.repos.d/passenger.repo



%changelog
* Thu Jan  6 2011 Erik Ogan <erik@stealthymonkeys.com> - 3-5
- Work around RHEL5's busted RPM/GPG support

* Wed Nov 24 2010 Erik Ogan <erik@stealthymonkeys.com> - 3-4
- Fix EL6 & FC14 version numbers.
- Fix the errant /en in the mirrors file

* Thu Oct 28 2010 Erik Ogan <erik@stealthymonkeys.com> - 3-3
- Typo in the gpgkey directives

* Thu Oct 28 2010 Erik Ogan <erik@stealthymonkeys.com> - 3-2
- Update the mirrorlist URL

* Tue Oct 26 2010 Erik Ogan <erik@stealthymonkeys.com> - 3-1
- Initial build.
