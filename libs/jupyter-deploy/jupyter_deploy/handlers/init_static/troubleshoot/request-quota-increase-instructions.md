Request a higher limit (replace the service code, quota code, value, and region):

```bash
aws service-quotas request-service-quota-increase \
  --service-code <service-code> --quota-code <quota-code> \
  --desired-value <value> --region <region>
```

Check the current value with `get-service-quota` and track the request with
`list-requested-service-quota-change-history-by-quota` (same `--service-code`
and `--quota-code`). Increases may require AWS support review and are not
instantaneous. The AWS Service Quotas console offers the same actions.
