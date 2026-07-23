---
name: helper
description: A skill that helps with data tasks and processing and other things.
---

# Flawed Skill (fixture: deliberately defective)

You are an AI assistant that helps the user. Always be helpful and do your best
to assist with the task at hand. Make sure to write clean code and follow best
practices. Be careful with edge cases and always test your changes before
finishing.

## Workflow

To process the data, always run exactly these steps in order every single time:

1. `cd C:\data\input`
2. `mkdir output`
3. `cp *.csv output\`
4. `cd output`
5. `python process.py --threshold 0.7 --window 42 --mode 3`
6. `cat result.json`

Follow these steps precisely. Do not deviate. The process never changes.

## Notes

Use good judgment. Write maintainable code. Ensure quality. Handle errors
appropriately. Remember to consider the user's needs.
