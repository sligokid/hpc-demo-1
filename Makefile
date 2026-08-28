.PHONY: test test-shell

# Run the bats shell-script test suite.
# Install bats first: brew install bats-core  (macOS)  |  apt-get install bats  (Debian/Ubuntu)
test-shell:
	bats tests/

# Alias
test: test-shell
