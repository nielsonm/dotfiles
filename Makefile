.PHONY: install uninstall diff sync cron check-secrets test help

help:
	@echo "Available commands:"
	@echo "  make install       - Run dotfiles installer with symlinks (macOS & Linux)"
	@echo "  make uninstall     - Remove symlinks and restore original .bak files"
	@echo "  make diff          - Show diff report between active config and repo"
	@echo "  make sync          - Pull active configs, check for secrets, commit & push"
	@echo "  make cron          - Install daily cron job for automatic sync"
	@echo "  make check-secrets - Scan repo and active configs for secrets and SSH keys"
	@echo "  make test          - Run full Python unit test suite"

install:
	./install.sh

uninstall:
	./uninstall.sh

diff:
	./check_diffs.sh

sync:
	./sync_active_config.sh

cron:
	./sync_active_config.sh --install-cron

check-secrets:
	./check_secrets.sh

test:
	python3 -m unittest discover tests
