# Ama Custom GPT schema validation note

Custom GPT Action schema v0.1.1 defines `components.schemas` as an object and gives every `type: object` schema explicit `properties`. This addresses the GPT editor validation error reported for v0.1.0 while leaving the hosted API behavior unchanged.
