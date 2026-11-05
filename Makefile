.PHONY: install uninstall deb rpm

package = packui_1.0.0_amd64
vendor_path = /usr/lib/packui/vendor

install:
	mkdir -p /usr/share/icons/hicolor/256x256/apps
	mkdir -p $(vendor_path)
	python3 -m pip install --disable-pip-version-check --no-compile --target $(vendor_path) -r $(runtime_requirements)
	cp packui.png /usr/share/icons/hicolor/256x256/apps/
	cp packui.desktop /usr/share/applications/
	cp packui.py /usr/local/bin/packui
	chmod +x /usr/local/bin/packui

uninstall:
	rm -f /usr/local/bin/packui
	rm -rf /usr/lib/packui
	rm -rf /opt/packui
	rm -f /usr/share/icons/hicolor/256x256/apps/packui.png
	rm -f /usr/share/applications/packui.desktop

deb:
	rm -rf $(package)/usr/lib/packui/vendor
	mkdir -p $(package)/usr/local/bin/
	mkdir -p $(package)/usr/lib/packui/vendor/
	mkdir -p $(package)/usr/share/icons/hicolor/256x256/apps/
	mkdir -p $(package)/usr/share/applications/
	python3 -m pip install --disable-pip-version-check --no-compile --target $(package)/usr/lib/packui/vendor -r $(runtime_requirements)
	cp packui.py $(package)/usr/local/bin/packui
	chmod +x $(package)/usr/local/bin/packui
	cp packui.png $(package)/usr/share/icons/hicolor/256x256/apps/
	cp packui.desktop $(package)/usr/share/applications/
	dpkg-deb --build --root-owner-group $(package)

rpm:
	rm -rf rpmbuild
	mkdir -p rpmbuild/SOURCES/packui
	python3 -m pip install --disable-pip-version-check --no-compile --target rpmbuild/SOURCES/packui -r $(runtime_requirements)
	tar -C rpmbuild/SOURCES -czf rpmbuild/SOURCES/packui.tar.gz packui
	cp packui.py packui.png packui.desktop rpmbuild/SOURCES/
	rpmbuild -bb --define "_topdir $(shell pwd)/rpmbuild" packui.spec
	cp rpmbuild/RPMS/x86_64/*.rpm .
	rm -rf rpmbuild
