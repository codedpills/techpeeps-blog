.DEFAULT_GOAL := help

# All Python runs through a project-local virtualenv so macOS/Homebrew's
# PEP 668 "externally-managed-environment" rule never blocks installs.
VENV := .venv
PY := $(VENV)/bin/python

.PHONY: help fetch transcribe generate next style-guide clip publish compare teaser newsletter remap refresh-meta patch-dates verify site-dev site-build install venv

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

$(PY):
	python3 -m venv $(VENV)

venv: $(PY) ## Create the .venv (done automatically by install)

install: $(PY) ## Create .venv and install Python + Node deps
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt
	npm install

fetch: ## Refresh the playlist into state.json
	$(PY) pipeline/fetch_playlist.py

transcribe: ## Transcribe next pending (ID=<id>, FORCE=1 to re-transcribe)
	$(PY) pipeline/transcribe.py $(if $(ID),$(ID),--next) $(if $(FORCE),--force)

remap: ## Re-run HOST/GUEST mapping on existing transcripts (no API cost; ID= optional)
	$(PY) pipeline/transcribe.py --remap $(ID)

refresh-meta: ## Fetch video publish dates into transcripts + state (no re-transcribe; ID= optional)
	$(PY) pipeline/transcribe.py --refresh-meta $(ID)

patch-dates: ## Backfill interviewDate onto existing drafted PR branches (run refresh-meta first)
	$(PY) pipeline/patch_meta.py $(if $(ID),$(ID),--all-drafted)

verify: ## Verify published posts against transcripts (quotes verbatim, frontmatter, clip)
	$(PY) pipeline/verify_post.py --all

style-guide: ## Build style-guide.md from the longest 3-4 transcripts
	$(PY) pipeline/make_style_guide.py --auto

generate: ## Draft + PR for next transcribed (ID=<id>, FORCE=1 redo, NOPR=1 local-only)
	$(PY) pipeline/generate.py $(if $(ID),$(ID),--next) $(if $(FORCE),--force) $(if $(NOPR),--no-pr)

compare: ## A/B two models on one transcript (ID=<id>, optional MODELS=a,b) — no git/PR
	$(PY) pipeline/compare_models.py $(ID) $(if $(MODELS),--models $(MODELS))

teaser: ## Preview the newsletter teaser for a published post: make teaser SLUG=<slug>
	$(PY) pipeline/teaser.py src/content/blog/$(SLUG).md --site $${SITE_URL:-https://techpeeps.example.com}

newsletter: ## Create a MailerLite campaign for a post (SLUG=<slug>; add SEND=1 to send now)
	$(PY) pipeline/send_newsletter.py src/content/blog/$(SLUG).md $(if $(SEND),--send)

next: ## Transcribe + generate + open PR for the next unprocessed video
	$(PY) pipeline/transcribe.py --next && $(PY) pipeline/generate.py --next

clip: ## Re-cut a hero clip: make clip ID=<id> START=MM:SS END=MM:SS SLUG=<slug>
	$(PY) pipeline/clip.py $(ID) --start $(START) --end $(END) --slug $(SLUG)

publish: ## Mark a merged video published: make publish ID=<video_id>
	$(PY) pipeline/mark_published.py $(ID)

site-dev: ## Run the Astro dev server
	npm run dev

site-build: ## Build the static site (fails on invalid frontmatter)
	npm run build
