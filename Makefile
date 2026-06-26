.DEFAULT_GOAL := help
PY := python3

.PHONY: help fetch transcribe generate next style-guide clip publish site-dev site-build install

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install Python + Node deps
	$(PY) -m pip install -r requirements.txt
	npm install

fetch: ## Refresh the playlist into state.json
	$(PY) pipeline/fetch_playlist.py

transcribe: ## Transcribe the next pending video (override with ID=<video_id>)
	$(PY) pipeline/transcribe.py $(if $(ID),$(ID),--next)

style-guide: ## Build style-guide.md from the longest 3-4 transcripts
	$(PY) pipeline/make_style_guide.py --auto

generate: ## Draft + open PR for the next transcribed video (override with ID=)
	$(PY) pipeline/generate.py $(if $(ID),$(ID),--next)

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
