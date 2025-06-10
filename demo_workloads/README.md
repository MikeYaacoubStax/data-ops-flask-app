# Long-Running Demo Workloads

This directory contains modified versions of NoSQLBench workloads designed for long-running demonstrations. These workloads are based on the baseline workloads but configured to run continuously until manually stopped.

## Overview

The workloads are designed with two main phases:
1. **Rampup Phase**: Initial data loading with a finite number of cycles
2. **Main Phase**: Long-running operations with very high cycle counts (`3B` - 3 billion cycles)

## JDBC Workloads

### JDBC Analytics Long-Running Workload

**File**: `jdbc_analytics_longrun.yaml`

This workload demonstrates TPC-H inspired analytical queries running continuously against PrestoDB.

#### Setup Commands (Run Once)

```bash
# 1. Drop existing tables (if any)
nb5 "long demo/jdbc_analytics_longrun.yaml" default.drop \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true

# 2. Create schema and tables
nb5 "long demo/jdbc_analytics_longrun.yaml" default.schema \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true

# 3. Load initial data (rampup phase)
nb5 "long demo/jdbc_analytics_longrun.yaml" default.rampup \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true \
  threads=10 \
  rampup_cycles=10000
```

#### Long-Running Analytics Phase

```bash
# Start continuous analytics queries (runs until stopped with Ctrl+C)
nb5 "long demo/jdbc_analytics_longrun.yaml" default.analytics \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true \
  threads=5 \
  analytics_cycles=3B
```

### JDBC E-commerce Long-Running Workload

**File**: `jdbc_ecommerce_longrun.yaml`

This workload simulates continuous e-commerce operations with transactional and analytical queries.

#### Setup Commands (Run Once)

```bash
# 1. Drop existing tables (if any)
nb5 "long demo/jdbc_ecommerce_longrun.yaml" default.drop \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true

# 2. Create schema and tables
nb5 "long demo/jdbc_ecommerce_longrun.yaml" default.schema \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true

# 3. Load initial data (rampup phase)
nb5 "long demo/jdbc_ecommerce_longrun.yaml" default.rampup \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true \
  threads=1 \
  rampup_cycles=25000
```

#### Long-Running Transaction Phase

```bash
# Start continuous transactional queries (runs until stopped with Ctrl+C)
nb5 "long demo/jdbc_ecommerce_longrun.yaml" default.transactions \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true \
  threads=1 \
  transaction_cycles=3B
```

#### Long-Running Analytics Phase

```bash
# Start continuous analytics queries (runs for 3 billion cycles)
nb5 "long demo/jdbc_ecommerce_longrun.yaml" default.analytics \
  dburl=jdbc:presto://52.204.216.32:8080/memory?user=testuser \
  use_hikaricp=true \
  threads=1 \
  transaction_cycles=3B
```

## OpenSearch Workloads

### OpenSearch Vector Search Long-Running Workload

**File**: `opensearch_vector_search_longrun.yaml`

This workload demonstrates continuous KNN vector search operations.

#### Setup Commands (Run Once)

```bash
# 1. Clean up any existing indices
nb5 "long demo/opensearch_vector_search_longrun.yaml" default.pre_cleanup \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200

# 2. Create vector index
nb5 "long demo/opensearch_vector_search_longrun.yaml" default.schema \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200

# 3. Load vector data (rampup phase)
nb5 "long demo/opensearch_vector_search_longrun.yaml" default.rampup \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200 \
  threads=20 \
  doc_count=10000
```

#### Long-Running Vector Search Phase

```bash
# Start continuous vector searches (runs until stopped with Ctrl+C)
nb5 "long demo/opensearch_vector_search_longrun.yaml" default.search \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200 \
  threads=10 \
  search_count=3B
```

### OpenSearch Basic Long-Running Workload

**File**: `opensearch_basic_longrun.yaml`

This workload demonstrates continuous basic CRUD operations.

#### Setup Commands (Run Once)

```bash
# 1. Clean up any existing indices
nb5 "long demo/opensearch_basic_longrun.yaml" default.pre_cleanup \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200

# 2. Create index
nb5 "long demo/opensearch_basic_longrun.yaml" default.schema \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200

# 3. Load initial data (rampup phase)
nb5 "long demo/opensearch_basic_longrun.yaml" default.rampup \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200 \
  threads=10 \
  doc_count=1000
```

#### Long-Running Search Phase

```bash
# Start continuous searches (runs until stopped with Ctrl+C)
nb5 "long demo/opensearch_basic_longrun.yaml" default.search \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200 \
  threads=5 \
  search_count=3B
```

### OpenSearch Bulk Long-Running Workload

**File**: `opensearch_bulk_longrun.yaml`

This workload demonstrates continuous bulk operations and verification.

#### Setup Commands (Run Once)

```bash
# 1. Clean up any existing indices
nb5 "long demo/opensearch_bulk_longrun.yaml" default.pre_cleanup \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200

# 2. Create bulk index
nb5 "long demo/opensearch_bulk_longrun.yaml" default.schema \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200

# 3. Load bulk data (rampup phase)
nb5 "long demo/opensearch_bulk_longrun.yaml" default.bulk_load \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200 \
  threads=5 \
  doc_count=100000
```

#### Long-Running Verification Phase

```bash
# Start continuous verification queries (runs until stopped with Ctrl+C)
nb5 "long demo/opensearch_bulk_longrun.yaml" default.verify \
  driver=opensearch \
  host=52.204.216.32 \
  port=9200 \
  threads=2 \
  verify_count=3B
```

## Cassandra Workloads

### SAI (Storage Attached Index) Long-Running Workload

**File**: `sai_longrun.yaml`

This workload demonstrates continuous SAI index operations with range queries, list containment searches, and numeric range filtering. All queries include `ALLOW FILTERING` to handle Cassandra's data filtering requirements.

#### Setup Commands (Run Once)

```bash
# 1. Create keyspace, tables, and SAI indices
nb5 "long demo/sai_longrun.yaml" setup.schema \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=sai_test \
  localdc=datacenter1

# 2. Load initial data (rampup phase)
nb5 "long demo/sai_longrun.yaml" setup.rampup \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=sai_test \
  localdc=datacenter1 \
  threads=auto \
  cycles=10000
```

#### Long-Running SAI Reads Phase

```bash
# Start continuous SAI read operations (runs for 3 billion cycles)
nb5 "long demo/sai_longrun.yaml" sai_reads_test.sai_reads \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=sai_test \
  localdc=datacenter1 \
  threads=auto \
  cycles=3B \
  ts_window=10 \
  prior_inserts=10000 \
  price_window=10
```

### LWT (Lightweight Transactions) Long-Running Workload

**File**: `lwt_longrun.yaml`

This workload demonstrates continuous LWT operations with complex conditional updates, batched transactions, and concurrent shard management.

#### Setup Commands (Run Once)

```bash
# 1. Create keyspace and tables
nb5 "long demo/lwt_longrun.yaml" setup.schema \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=lwt_ks \
  localdc=datacenter1

# 2. Truncate tables (if needed)
nb5 "long demo/lwt_longrun.yaml" setup.truncating \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=lwt_ks \
  localdc=datacenter1 \
  threads=1

# 3. Initialize shards
nb5 "long demo/lwt_longrun.yaml" setup.sharding \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=lwt_ks \
  localdc=datacenter1 \
  threads=8 \
  cycles=80 \
  cyclerate=10 \
  stride_constant=1 \
  shard_range_size=80

# 4. Load initial LWT data
nb5 "long demo/lwt_longrun.yaml" setup.lwt_load \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=lwt_ks \
  localdc=datacenter1 \
  shard_range_size=80 \
  stride_constant=384 \
  update_ratio=75 \
  non_repeating_statements=9 \
  repeating_statements=5 \
  cyclerate=1000 \
  cycles=100000 \
  threads=auto
```

#### Long-Running LWT Updates Phase

```bash
# Start continuous LWT operations (runs until stopped with Ctrl+C)
nb5 "long demo/lwt_longrun.yaml" lwt-updates.lwt_live_update \
  driver=cql \
  host=127.0.0.1 \
  port=9042 \
  keyspace=lwt_ks \
  localdc=datacenter1 \
  cycles=3000000000 \
  threads=auto \
  shard_range_size=80 \
  max_rounds=3 \
  max_tasks=225 \
  stride_constant=1 \
  shard_offset=0 \
  update_ratio=75 \
  non_repeating_statements=9 \
  repeating_statements=5
```

## Key Modifications for Long-Running Operation

1. **High Cycle Counts**: Main phases use `cycles=3B` (3 billion cycles) for very long-running operation
2. **Unique Index Names**: OpenSearch workloads use `_longrun` suffix to avoid conflicts
3. **Separate Phases**: Clear separation between setup (finite) and long-running (high cycle count) phases
4. **Template Variables**: Allow customization of cycle counts via command-line parameters
5. **Keyspace Creation**: Cassandra workloads now include automatic keyspace creation with SimpleStrategy replication

## Stopping Long-Running Workloads

All long-running phases will continue for 3 billion cycles or until manually stopped. Use `Ctrl+C` to stop the workload gracefully.

## Cleanup

After demonstrations, clean up resources:

```bash
# JDBC - Drop schemas
nb5 "long demo/jdbc_analytics_longrun.yaml" default.drop dburl=jdbc:presto://...
nb5 "long demo/jdbc_ecommerce_longrun.yaml" default.drop dburl=jdbc:presto://...

# OpenSearch - Delete indices
nb5 "long demo/opensearch_vector_search_longrun.yaml" default.cleanup driver=opensearch host=...
nb5 "long demo/opensearch_basic_longrun.yaml" default.cleanup driver=opensearch host=...
nb5 "long demo/opensearch_bulk_longrun.yaml" default.cleanup driver=opensearch host=...

# Cassandra - Drop keyspaces (optional)
# Note: These commands will drop entire keyspaces - use with caution
# DROP KEYSPACE sai_test;
# DROP KEYSPACE lwt_ks;
```
