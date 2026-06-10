The `cluster` commands operate on the Kubernetes cluster — here a cluster managed by
AWS EKS — that hosts your apps.

`jd cluster login` configures your local `kubeconfig` so that `kubectl` talks to this
cluster. After running it, `kubectl` commands target the EKS cluster, and you can confirm
your Kubernetes identity with `kubectl auth whoami`.

```bash
# point kubectl at this cluster (writes to ~/.kube/config)
jd cluster login

# confirm kubectl is now talking to the cluster as you
kubectl auth whoami

# check the cluster control plane status, or show its details (endpoint, version)
jd cluster status
jd cluster show
```
