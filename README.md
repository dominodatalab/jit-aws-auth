
# JIT Installation Instructions

## Pre-requisites

Turn on [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) for your EKS cluster 

## Installation Prep Steps (AWS)

This is a list of steps and checks to follow as a preparatory step for installing JIT

1. Verify that the namespace domino-field exists in the EKS cluster or create one . 
```shell
kubectl get namespace domino-field
# or 
kubectl create namespace domino-field
```

If the namespace exists, ensure that it has a label of `domino-compute=true`.
```shell
kubectl label ns domino-field domino-compute=true
```

For Istio-enabled deployments, also add the Istio sidecar injection label:

```shell
kubectl label ns domino-field istio-injection=enabled
```

2. Ensure that the compute (default: `domino-compute`) namespace has the label `operator-enabled=true`:

```shell
kubectl label ns domino-compute operator-enabled="true"
```


3. Create two secrets in the AWS Secrets 
   a. `dev/nuid`
   b. `dev/ping/client`



4. Next define roles (One for the secret in each environment) . An example in the Domino account has name `domino-jit-role` and has the following policy with name `domino-jit-policy` attached to it 
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "secretsmanager:DescribeSecret"
            ],
            "Resource": [
                "arn:aws:secretsmanager:<AWS_REGION>:<EKS_ACCOUNT_NO>:secret:dev/nuid-SIHUKk",
                "arn:aws:secretsmanager:<AWS_REGION>:<EKS_ACCOUNT_NO>:secret:dev/ping/client-R3cHbp"
            ]
        }
    ]
}
```


5. The role definition along with its trust policy is defined as follows. Make the appropriate changes for Fannie Mae environment
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Federated": "arn:aws:iam::<EKS_ACCOUNT>:oidc-provider/oidc.eks.us-west-2.amazonaws.com/id/0F5496F958BA342AF97XXXXXXXX"
            },
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {
                "StringEquals": {
                    "oidc.eks.us-west-2.amazonaws.com/id/0F5496F958BA342AF97XXXXXXXX:aud": "sts.amazonaws.com",
                    "oidc.eks.us-west-2.amazonaws.com/id/0F5496F958BA342AF97XXXXXXXX:sub": "system:serviceaccount:domino-field:jit"
                }
            }
        }
    ]
}
```

Note the OIDC connect provider Id (`0F5496F958BA342AF97XXXXXXXX`) . You will need to replace it with the appropriate one. The one provided is for the cluster aws-iam7653.
You can find the provider id with the following command (requires the AWS CLI and the `jq` command):

```shell
aws eks describe-cluster --name <CLUSTER_NAME> | jq -r '.cluster.identity.oidc.issuer' | rev | cut -d '/' -f1 | rev
```

6. Installation of the AWS Secrets and Configuration Provider (ASCP)

Complete documentation can be found [here](https://docs.aws.amazon.com/secretsmanager/latest/userguide/integrating_csi_driver.html#integrating_csi_driver_example_2).

From the base of this repo, cd to `helm/secrets-store-csi-driver`. Copy the `values.yaml` file to `values-deploy.yaml`, and 
update `values-deploy.yaml`. Modify `values-deploy.yaml` as needed (e.g. if you're using a private container repo, modify the various `repository` values).

Install the base CSI driver as follows:

```shell
helm install -n kube-system csi-secrets-store -f values-deploy.yaml .
```

Now, we will need to install the AWS provider for the CSI driver. From the base of this repo, cd to `helm/secrets-store-csi-driver-provider-aws`. Copy the `values.yaml` file to `values-deploy.yaml`, and update `values-deploy.yaml`. Modify `values-deploy.yaml` as needed (e.g. if you're using a private container repo, modify the various `repository` values).

```shell
helm install -n kube-system secrets-provider-aws -f values-deploy.yaml .
```

Alternatively you can follow the installation process in the link and run the following (requires internet access):
```shell
helm repo add secrets-store-csi-driver https://kubernetes-sigs.github.io/secrets-store-csi-driver/charts
helm install -n kube-system csi-secrets-store \
  --set syncSecret.enabled=true \
  --set enableSecretRotation=true \
  secrets-store-csi-driver/secrets-store-csi-driver
helm upgrade -n kube-system csi-secrets-store \
  --set syncSecret.enabled=true \
  --set enableSecretRotation=true \
  secrets-store-csi-driver/secrets-store-csi-driver
helm repo add aws-secrets-manager https://aws.github.io/secrets-store-csi-driver-provider-aws
helm install -n kube-system secrets-provider-aws aws-secrets-manager/secrets-store-csi-driver-provider-aws

```


7. Install the secrets provider in K8s. You will need to change the ARN of the secret

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: jit-data
  namespace: domino-field
spec:
  provider: aws
  parameters:
    objects: |
      - objectName: "arn:aws:secretsmanager:<AWS_REGION>:<EKS_ACCOUNT_NO>:secret:dev/nuid-SIHUKk"
        objectType: "secretsmanager"
        objectAlias: "nuid"
      - objectName: "arn:aws:secretsmanager:<AWS_REGION>:<EKS_ACCOUNT_NO>:secret:dev/ping/client-R3cHbp"
        objectType: "secretsmanager"
        objectAlias: "ping-client"
```

### Smoke Test

1. Create a Service Account in K8s as follows 
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: jit
  namespace: domino-field
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::<EKS_ACCOUNT_NO>:role/dev-domino-jit-role
```

2. Create the following pod (this step requires that you have access to a container repo with the `nginx` container - if you don't have such, this step can be skipped):
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx
  namespace: domino-field
  labels:
    app: nginx
spec:
  serviceAccountName: jit
  volumes:
  - name: jit-data
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
      volumeAttributes:
        secretProviderClass: "jit-data"
  containers:
  - name: nginx
    image: nginx
    volumeMounts:
      - name: jit-data
        mountPath: "/etc/config"
```


3. Verify that the secrets are loaded (if you skipped step two above, skip down to "Install the JIT components" below)

```shell
kubectl -n domino-field exec -it nginx -c nginx -- ls -l /etc/config/

kubectl -n domino-field  exec -it nginx -c nginx -- cat  /etc/config/nuid/nuid

kubectl -n domino-field  exec -it nginx -c nginx -- cat  /etc/config/ping/ping-client
```

4. Clean up
```shell
kubectl -n domino-field delete -f .
```

## Install the JIT components

1. Install `domsed`

Domsed is a Domino tool to mutate pods according to a set of rules. This is what will hook in the JIT client sidecar to workspaces.

From the base of this repo, `cd` to `helm/domsed`. Copy the `values.yaml` file to `values-deploy.yaml`, and update `values-deploy.yaml` to account for changes in your container repo URL (`.image.repository`), as well as any environment-specific modifications that may be needed (e.g. Istio-awareness, log level, etc.). Once this file is ready, run the following command to install:

```shell
helm -n domino-platform upgrade --install domsed -f values-deploy.yaml .
```

2. Validate that domsed is running:

```shell
kubectl get pods -A -l app=operator-webhook
```

3.  Install `jit`

From the base of this repo, `cd` to `helm/jit`. Copy the `values.yaml` file to `values-deploy.yaml`, and update `values-deploy.yaml` to account for changes in your container repo URL (`.image.repository`), as well as any environment-specific modifications that may be needed (e.g. IAM role-arn from the pre-requisites steps above, the file location for the JIT API CA cert, etc). Once this file is ready, run the following command to install:

```shell
helm -n domino-field upgrade --install jit -f values-deploy.yaml .
```

4. Validate that the JIT Proxy API is running:

```shell
kubectl -n domino-field get pods -l app=jit
```

## Troubleshooting

### Client-side

Assuming that the setup above ran normally, you'll want to start a new workspace. You should be able to see credentials within the file `/etc/.aws/credentials`. If you don't, you'll need to start troubleshooting by looking through the client logfile from within the workspace. This can be found at `/var/log/jit/app.log`. From within your workspace, you can `cat /var/log/jit/app.log` to grab the client-side logs.

### JIT Proxy Server

The log for the API proxy server is both within the pod stdout, as well as the file `/var/log/jit/app.log` in the pod. The proxy server has two logging locations: basic logs are emitted to stdout, but more complex errors may be found by running `kubectl -n domino-field exec -it <JIT_POD_NAME> -c jit -- cat /var/log/jit/app.log | grep -v healthz`. You can get `<JIT_POD_NAME>` by running `kubectl -n domino-field get pods -l app=jit`.

Within both the client and proxy server, you can set an environment variable of `LOG_LEVEL=DEBUG` to emit additional logs. This should **only** be done during troubleshooting sessions, as it can result in sensitive data being emitted to logs. To set this log level in the proxy server, modify the `Deployment` named `jit` in `domino-field`. To modify the log level in the client-side container, modify the `Mutation` `jit` in the platform namespace.

## AWS Secret Rotation considerations

Periodically, the secret data within AWS Secrets Manager will be rotated. As of this writing, the JIT Proxy server does not automatically reload its configuration when the underlying Secrets Manager data is changed. To pull in the new secret data, restart the JIT Proxy server:

```shell
kubectl -n domino-field delete pod -l app=jit
```