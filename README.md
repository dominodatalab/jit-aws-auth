
# JIT Installation Instructions

## Pre-requiste

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

2. Create two secrets in the AWS Secrets 
   a. `dev/nuid`
   b. `dev/ping/client`



3. Next define roles (One for the secret in each environment) . An example in the Domino account has name `domino-jit-role` and has the following policy with name `domino-jit-policy` attached to it 
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


4. The role definition along with its trust policy is defined as follows. Make the appropriate changes for Fannie Mae environment
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

5. Installation of the AWS Secrets and Configuration Provider (ASCP)

Complete documentation can be found [here](https://docs.aws.amazon.com/secretsmanager/latest/userguide/integrating_csi_driver.html#integrating_csi_driver_example_2).

The only modification recommended is to replace the command
```shell
helm install -n kube-system csi-secrets-store secrets-store-csi-driver/secrets-store-csi-driver
```
with
```shell
helm install -n kube-system csi-secrets-store \
  --set syncSecret.enabled=true \
  --set enableSecretRotation=true \
  secrets-store-csi-driver/secrets-store-csi-driver
```

Alternatively you can follow the installation process in the link and run the following
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


6. Install the secrets provider in K8s. You will need to change the ARN of the secret

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

## Smoke Test

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

2. Create the following pod 
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


3. Verify that the secrets are loaded 

```shell
kubectl -n domino-field exec -it nginx -c nginx -- ls -l /etc/config/

kubectl -n domino-field  exec -it nginx -c nginx -- cat  /etc/config/nuid/nuid

kubectl -n domino-field  exec -it nginx -c nginx -- cat  /etc/config/ping/ping-client
```

4. Clean up
```shell
kubectl -n domino-field delete -f .
```
