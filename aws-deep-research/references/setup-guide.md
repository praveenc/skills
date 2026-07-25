# First-Run Setup Guide

This guide runs once when the external machine-local config has not been
created or still matches the template.

Default path: `~/.config/aws-deep-research/config.env`.
Override it with `AWS_DEEP_RESEARCH_CONFIG`.
Never store credentials inside the skill directory.

## Detection

```bash
CONFIG_FILE="${AWS_DEEP_RESEARCH_CONFIG:-$HOME/.config/aws-deep-research/config.env}"
if [ -f "$CONFIG_FILE" ]; then
  diff -q "$CONFIG_FILE" "$SKILL_DIR/scripts/.env.example" >/dev/null 2>&1
  echo "ENV_CUSTOMIZED=$?"
else
  echo "ENV_CUSTOMIZED=1"
fi
```

- Exit `0` (identical) - run setup below
- Exit `1` (missing or different) - create/configure as needed

## Setup Message

Show the user:

> 👋 **First-time setup for AWS Deep Research**
>
> This skill uses optional API keys for web search and GitHub search.
> AWS documentation, blog feeds, and MCP-based sources work without any keys.
>
> **Optional API keys** (add to `~/.config/aws-deep-research/config.env`):
>
> | Service | Free Tier | Credit Card? | Sign Up |
> |---------|-----------|-------------|---------|
> | Tavily Search | 1,000 credits/month | ❌ No | [Quickstart](https://docs.tavily.com/documentation/quickstart) |
> | Brave Search | 2,000 requests/month | ✅ Yes | [API signup](https://brave.com/search/api/) |
> | GitHub | Unlimited (public repos) | ❌ No | [Create token](https://github.com/settings/tokens) |
>
> Would you like to add any keys now, or proceed without them?

If the user provides keys, create the parent directory with mode `700`, write
`CONFIG_FILE` with mode `600`, and update it without echoing values.

Also ask:

> **Report output directory**: Final reports are saved to a global folder
> for safekeeping. Default: `~/.aws-deep-research/outputs`
>
> Would you like to use a different path?

If yes, update `REPORT_OUTPUT_DIR` in `CONFIG_FILE`. Otherwise keep the default.
Then proceed to Step 1.
