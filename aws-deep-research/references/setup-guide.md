# First-Run Setup Guide

This guide runs once — when `$SKILL_DIR/scripts/.env` has never been customized.

## Detection

```bash
diff -q "$SKILL_DIR/scripts/.env" "$SKILL_DIR/scripts/.env.example" >/dev/null 2>&1
echo "ENV_CUSTOMIZED=$?"
```

- Exit `0` (identical) → run setup below
- Exit `1` (differ) → already configured, skip to Step 1

## Setup Message

Show the user:

> 👋 **First-time setup for AWS Deep Research**
>
> This skill uses optional API keys for web search and GitHub search.
> AWS documentation, blog feeds, and MCP-based sources work without any keys.
>
> **Optional API keys** (add to `$SKILL_DIR/scripts/.env`):
>
> | Service | Free Tier | Credit Card? | Sign Up |
> |---------|-----------|-------------|---------|
> | Tavily Search | 1,000 credits/month | ❌ No | [Quickstart](https://docs.tavily.com/documentation/quickstart) |
> | Brave Search | 2,000 requests/month | ✅ Yes | [API signup](https://brave.com/search/api/) |
> | GitHub | Unlimited (public repos) | ❌ No | [Create token](https://github.com/settings/tokens) |
>
> Would you like to add any keys now, or proceed without them?

If the user provides keys, update `.env` accordingly.

Also ask:

> **Report output directory**: Final reports are saved to a global folder
> for safekeeping. Default: `~/.aws-deep-research/outputs`
>
> Would you like to use a different path?

If yes, update `REPORT_OUTPUT_DIR` in `.env`. Otherwise keep the default.
Then proceed to Step 1.
