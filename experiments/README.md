# Experiments

Prototypes, tools, and side explorations that don't fit the other categories — hands-on experiments that compare approaches and produce reproducible, honest numbers.

## Projects

- **[Query engine benchmark](query-engine-benchmark/)** — pandas, Polars, and DuckDB head-to-head on 5 million synthetic orders: six realistic analytics queries, cross-engine result verification, and measured timings and peak memory. DuckDB was fastest on the filter, join, and top-N with ~2.2× less peak memory than pandas; Polars won load time and the group-bys.

New experiments are added here as they are completed.
