# AWS Security Blog Digest: March 10-14, 2026

**Date:** March 2026
**Sources:** [AWS Security Blog](https://aws.amazon.com/blogs/security/)

## Overview

Three posts from the AWS Security Blog covering multi-Region resilience, supply chain security, and European sovereign cloud compliance.

## Post 1: Multi-Region IAM Identity Center

**Title:** Workforce Access That Survives Regional Outages
**Author:** Alex Milanovic | **Published:** Mar 14, 2026
**URL:** https://aws.amazon.com/blogs/security/multi-region-iam-identity-center

IAM Identity Center now supports multi-Region replication. When the primary Region goes down, users continue authenticating through the additional Region. The post covers configuring multi-Region customer-managed KMS keys, enabling additional Regions in the console, and updating identity providers (Okta, Entra ID) with regional URLs.

**Key requirements:** Organization instance required, External IdP (Okta, Entra ID), Multi-Region KMS keys, Opt-in Regions not supported, Account instances not supported.

## Post 2: AMI Lineage with Graph Databases

**Title:** Tracing Machine Images Back to Source with Graph Databases
**Author:** George'son Tib | **Published:** Mar 12, 2026
**URL:** https://aws.amazon.com/blogs/security/ami-lineage-graph-databases

A solution built on Amazon Neptune that tracks AMI relationships across an organization. EventBridge forwards AMI lifecycle events to a centralized security account, Lambda processes them, and API Gateway exposes lineage queries. Security teams can trace any running AMI back to its golden image source, assess CVE blast radius, and enforce image policies.

**Architecture:** Amazon Neptune (graph DB), EventBridge (event routing), Lambda (event processing), API Gateway (lineage queries), Multi-account model.

## Post 3: European Sovereign Cloud Certifications

**Title:** European Sovereign Cloud Earns SOC 2, C5, and Seven ISO Certifications
**Author:** Julian Herlinghaus | **Published:** Mar 10, 2026
**URL:** https://aws.amazon.com/blogs/security/european-sovereign-cloud-certifications

The AWS European Sovereign Cloud, generally available since January 2026, has achieved its first compliance certifications: SOC 2 Type 1, C5 Type 1 (German BSI standard), and seven ISO certifications covering information security, privacy, business continuity, and quality management. Reports cover 69 AWS services and are accessible via AWS Artifact.

**Certifications:** SOC 2 Type 1, C5 Type 1 (BSI), ISO 27001/27017/27018, ISO 27701 (privacy), ISO 22301/20000-1/9001.
