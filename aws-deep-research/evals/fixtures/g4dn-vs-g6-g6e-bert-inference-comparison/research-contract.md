# G4dn vs G6/G6e for BERT Inference

**Scope:** Compare AWS EC2 g4dn, g6, and g6e instance families for BERT-style transformer inference workloads on throughput, latency, and cost.

**Intents:** comparison, pricing

**Entities to exclude:** Azure, GCP, on-prem GPUs

**Key questions:**
- How does BERT inference throughput differ across T4 (g4dn), L4 (g6), and L40S (g6e) GPUs?
- What is the On-Demand and discounted (Spot/Savings Plan) hourly cost for each family in us-east-1?
- Does the higher hourly price of g6/g6e translate into a lower cost-per-inference?
- Where do vendor throughput claims (e.g. "up to 4x") diverge from independently measured benchmarks?
- What network/memory differences matter for batch vs. real-time inference?
