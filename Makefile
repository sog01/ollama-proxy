# ollama-proxy Makefile
# Bootstrap + run helpers for both services.

SHELL := /bin/bash
ROOT  := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

PROXY_DIR := $(ROOT)/proxy-inference
AI_DIR    := $(ROOT)/ai-inference

PROXY_VENV := $(PROXY_DIR)/venv
AI_VENV    := $(AI_DIR)/venv

PROXY_HOST ?= 0.0.0.0
PROXY_PORT ?= 8080

.PHONY: help \
        check-deps check-deps-proxy check-deps-ai \
        run-proxy run-ai \
        test test-version test-tags test-chat test-chat-stream test-generate test-generate-stream \
        clean clean-proxy clean-ai

help:
	@echo "ollama-proxy targets:"
	@echo "  make check-deps         Bootstrap system deps + both service venvs"
	@echo "  make check-deps-proxy   Bootstrap proxy-inference venv + deps + .env"
	@echo "  make check-deps-ai      Bootstrap ai-inference venv + deps + .env"
	@echo "  make run-proxy          Run proxy-inference (uvicorn) on $(PROXY_HOST):$(PROXY_PORT)"
	@echo "  make run-ai             Run ai-inference WS client"
	@echo "  make test               Run all curl smoke tests against the proxy"
	@echo "  make test-version       GET /api/version"
	@echo "  make test-tags          GET /api/tags"
	@echo "  make test-chat-stream   POST /api/chat  stream:true   (override MODEL=...)"
	@echo "  make test-chat          POST /api/chat  stream:false  (override MODEL=...)"
	@echo "  make test-generate-stream  POST /api/generate stream:true"
	@echo "  make test-generate         POST /api/generate stream:false"
	@echo "  make clean              Remove both venvs"

# ---- bootstrap ----

check-deps:
	@"$(ROOT)/scripts/check_deps.sh"

check-deps-proxy:
	@"$(PROXY_DIR)/scripts/check_deps.sh"

check-deps-ai:
	@"$(AI_DIR)/scripts/check_deps.sh"

# ---- run ----
# Auto-bootstrap venv if missing, then exec the service from inside it.

run-proxy: | $(PROXY_VENV)
	@cd "$(PROXY_DIR)" && \
		"$(PROXY_VENV)/bin/python" -m uvicorn src.main:app \
			--host $(PROXY_HOST) --port $(PROXY_PORT)

run-ai: | $(AI_VENV)
	@cd "$(AI_DIR)" && "$(AI_VENV)/bin/python" -m src.main

$(PROXY_VENV):
	@"$(PROXY_DIR)/scripts/check_deps.sh"

$(AI_VENV):
	@"$(AI_DIR)/scripts/check_deps.sh"

# ---- test (curl smoke) ----
# Pass MODEL=... and PROXY_URL=... on the command line to override.
# CLIENT_KEY is auto-read from proxy-inference/.env if unset.

test:
	@"$(ROOT)/scripts/test_curl.sh" all

test-version:
	@"$(ROOT)/scripts/test_curl.sh" version

test-tags:
	@"$(ROOT)/scripts/test_curl.sh" tags

test-chat:
	@"$(ROOT)/scripts/test_curl.sh" chat

test-chat-stream:
	@"$(ROOT)/scripts/test_curl.sh" chat-stream

test-generate:
	@"$(ROOT)/scripts/test_curl.sh" generate

test-generate-stream:
	@"$(ROOT)/scripts/test_curl.sh" generate-stream

# ---- clean ----

clean: clean-proxy clean-ai

clean-proxy:
	@rm -rf "$(PROXY_VENV)"
	@echo "removed $(PROXY_VENV)"

clean-ai:
	@rm -rf "$(AI_VENV)"
	@echo "removed $(AI_VENV)"
