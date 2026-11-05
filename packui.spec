Name:           packui
Version:        1.0.0
Release:        1%{?dist}
Summary:        PyQt6 interface for installed Linux package managers
License:        GPLv3
BuildArch:      x86_64

Source0:        packui.py
Source1:        packui.desktop

Requires:       python3 >= 3.9
Requires:       python3-pyqt6

%description
PackUI is a PyQt6 graphical interface for locally installed Linux package
managers. Package operations use the system's package managers, not store APIs.

%prep

%build

%install
install -Dm755 %{SOURCE0} %{buildroot}/usr/local/bin/packui
install -Dm644 %{SOURCE1} %{buildroot}/usr/share/applications/packui.desktop

%files
/usr/local/bin/packui
/usr/share/applications/packui.desktop
