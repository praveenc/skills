# Choosing an Amazon Bedrock inference access pattern

**Date:** August 2026
**Sources:** [Model invocation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation.html), [Provisioned Throughput](https://docs.aws.amazon.com/bedrock/latest/userguide/prov-throughput.html), [Cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)

## Executive summary

Teams that move a generative AI workload from a prototype to production must
choose how applications reach a model. Amazon Bedrock supports on-demand model
invocation, cross-Region inference profiles, and Provisioned Throughput. The
right choice depends on traffic shape, latency objectives, regional policy,
model availability, and the cost of unused capacity.

For most new workloads, start with on-demand invocation. It has no capacity
commitment and exposes the simplest operating model. Use cross-Region inference
when a supported profile can route traffic across permitted Regions and the
application values burst absorption more than strict single-Region processing.
Evaluate Provisioned Throughput when traffic is sustained, predictable, and
large enough to keep committed capacity busy.

This report does not claim that one access pattern is always cheaper. Prices,
supported models, inference-profile membership, and commitment terms can
change. Confirm those values when the decision is made.

## Decision context

The reference workload is a customer-support assistant in us-east-1. It serves
interactive requests during business hours and batch summarization overnight.
The service objective is 99.9% monthly availability. The interactive path has
a target time to first token below 700 milliseconds at the 95th percentile.
The batch path can wait up to 15 minutes before processing starts.

Traffic is uneven. Interactive demand averages 18 requests per second and
reaches 75 requests per second during product incidents. Batch demand can be
scheduled, but it competes with the interactive path if both use the same
quota. Prompt sizes vary from 1,500 to 18,000 input tokens. Response sizes vary
from 200 to 2,000 output tokens.

The security team permits processing in us-east-1 and us-west-2. It does not
permit processing outside the United States. The application team therefore
cannot assume that every cross-Region inference profile is acceptable. The
profile's destination Regions must be reviewed against the workload's data
handling policy.

## Option 1: on-demand invocation

On-demand invocation is the default starting point. The application sends a
request to a supported foundation model and pays for usage. The team does not
reserve model units or manage a capacity commitment.

The main benefit is flexibility. A prototype can change models or request
patterns without first purchasing capacity. Development, evaluation, and
low-volume production workloads can share the same basic invocation pattern.
The team can observe token demand before it commits to a longer-term capacity
decision.

The main constraint is quota and shared service capacity. A sudden traffic
increase can encounter throttling even when the long-term average is modest.
The application still needs bounded retries, backoff, admission control, and a
clear user response when capacity is unavailable. Raising a quota does not by
itself guarantee that every burst will complete without throttling.

On-demand is a good fit when demand is low, variable, or not yet measured. It
is also useful as an overflow path when the workload design and model terms
permit that pattern. The overflow claim must be verified for the selected
model and access configuration.

## Option 2: cross-Region inference

Cross-Region inference profiles can route requests to supported destination
Regions. This can give a workload access to a larger pool of capacity than a
single-Region request path. It can reduce throttling during bursts when the
profile and model support the required Regions.

This option changes the policy question. The application endpoint may be in
us-east-1, but processing can occur in another Region included in the profile.
Teams must review the current profile definition instead of inferring data
location from the endpoint alone.

Cross-Region inference can help the interactive path because incident traffic
is bursty. It does not remove the need for retries or load shedding. It also
does not guarantee a fixed latency improvement. Network path, model load,
prompt size, and destination selection can affect the result.

For the reference workload, a United States profile is a candidate only if its
documented destination Regions match the approved policy. The team must record
the profile identifier, supported model, destination list, and verification
date in the production decision.

## Option 3: Provisioned Throughput

Provisioned Throughput reserves model capacity for a selected model and term.
It is intended for workloads that need predictable throughput and can use the
committed capacity. The purchase and model support rules must be checked when
the team evaluates the option.

The main benefit is a capacity plan that is easier to align with a steady
production load. A team can separate a stable interactive base load from a
variable overflow path. This can make throttling behavior and cost attribution
easier to reason about.

The main risk is underuse. The batch workload creates a large daily token
volume, but it can move within a 15 minutes scheduling window. If the team buys
capacity for the combined peak and uses it only during short incidents, the
unused commitment can dominate the cost.

Before purchase, measure tokens per minute, request concurrency, prompt-size
distribution, response-size distribution, and model latency. Averages alone
are not enough. The team should replay representative traffic and determine
how much of the day can keep the provisioned model units busy.

## Recommended staged decision

Phase one should use on-demand invocation in us-east-1. Instrument token usage,
throttles, retries, time to first token, end-to-end latency, and rejected
requests. Separate interactive and batch measurements so one workload does not
hide the other's traffic shape.

Phase two should test a policy-approved cross-Region inference profile. Run the
same replay against on-demand single-Region access and the selected profile.
Compare throttling and latency distributions. Do not use one average latency
number as the decision.

Phase three should model Provisioned Throughput from observed demand. Compare
the committed capacity with the stable base load, not the largest incident
spike. Include the cost of unused capacity and the operational value of a more
predictable path.

The likely production design is a measured combination rather than a universal
winner. The interactive base load may justify provisioned capacity after demand
stabilizes. Cross-Region inference may absorb approved bursts. On-demand access
remains the simplest starting point while the team collects evidence.

## Evidence limits and review triggers

This report uses service behavior documented in August 2026. It does not freeze
the list of supported models, Regions, profiles, quotas, or prices. Recheck the
decision before launch and after any model change.

Review the decision when sustained token demand changes by 25%, the approved
Region list changes, the service objective changes, or a new model becomes the
primary production model. Also review it after a throttling event that affects
the 99.9% availability objective.

The final architecture record should name the model, access pattern, Region or
profile, verification date, retry policy, fallback behavior, capacity owner,
and the evidence used for the decision.
