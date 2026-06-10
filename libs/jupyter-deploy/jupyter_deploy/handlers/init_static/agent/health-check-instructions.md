The `health` command aggregates the status of the full deployment stack: the cluster
control plane, the load balancer target health, the platform components, and the
end-to-end connection.

```bash
# run all health checks
jd health

# narrow to a single layer
jd health --cluster
jd health --load-balancer
jd health --components
jd health --connection

# machine-readable output
jd health --json
```
