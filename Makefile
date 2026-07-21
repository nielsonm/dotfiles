.PHONY: install diff sync cron help

help:
	@echo "Available commands:"
	@echo "  make install  - Run dotfiles installer (macOS & Linux)"
	@echo "  make diff     - Show diff report between active config and repo"
	@echo "  make sync     - Pull active configs, commit to machine-date branch, and push"
	@echo "  make cron     - Install daily cron job for automatic sync"

install:
	./install.sh

diff:
	./check_diffs.sh

sync:
	./sync_active_config.sh

cron:
	./sync_active_config.sh --install-cron
