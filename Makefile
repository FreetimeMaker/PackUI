.PHONY: install uninstall deb rpm

package = packui_1.0.0_amd64

install:
	install -Dm755 packui.py $(DESTDIR)/usr/local/bin/packui
	install -Dm644 packui.desktop $(DESTDIR)/usr/share/applications/packui.desktop

uninstall:
	rm -f $(DESTDIR)/usr/local/bin/packui
	rm -f $(DESTDIR)/usr/share/applications/packui.desktop

deb:
	rm -rf $(package)/usr $(package)/opt
	$(MAKE) install DESTDIR=$(CURDIR)/$(package)
	dpkg-deb --build --root-owner-group $(package)

rpm:
	rm -rf rpmbuild
	mkdir -p rpmbuild/SOURCES
	cp packui.py packui.desktop rpmbuild/SOURCES/
	rpmbuild -bb --define "_topdir $(CURDIR)/rpmbuild" packui.spec
	cp rpmbuild/RPMS/x86_64/*.rpm .
	rm -rf rpmbuild
