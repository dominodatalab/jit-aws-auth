
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

2. Create two secrets in the AWS Secrets 
   a. `dev/nuid`
   b. `dev/ping/client`


2 (Optional). Create a Secret `domino/jit` in AWS Secrets Manager in the same region EKS is installed. We do not own this secret. The same values are just test values
```shell
{"root_cert":"test_contents","jit_endpoint":"http://www.google.com","token_endpoint":"http://www.google.com","client_id":"test_client_id","client_secret":"test_client_secret","r_username":"r_user","r_password":"r_password","minimum_token_validity_required_in_seconds":"300.0"}
```

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
                "arn:aws:secretsmanager:<AWS_REGION>:<EKS_ACCOUNT_NO>:secret:dev/domino/jit-kNnySv",
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

Note the OIDC connect provider Id (`0F5496F958BA342AF97XXXXXXXX`) . You will need to replace it with the appropriate one. The one provided is for the cluster aws-iam7653

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
helm upgrade -n kube-system csi-secrets-store \
  --set syncSecret.enabled=true \
  --set enableSecretRotation=true \
  secrets-store-csi-driver/secrets-store-csi-driver
```


6. Install the secrets provider in K8s. You will need to change the ARN of the secret


```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: jit-secrets
  namespace: domino-field
spec:
  provider: aws
  parameters:
    objects: |
      - objectName: "arn:aws:secretsmanager:us-west-2:<EKS_ACCOUNT_NO>:secret:dev/nuid-SIHUKk"
        objectType: "secretsmanager"
        objectAlias: "nuid"
---
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: jit-secrets
  namespace: domino-field
spec:
  provider: aws
  parameters:
    objects: |
      - objectName: "arn:aws:secretsmanager:us-west-2:<EKS_ACCOUNT_NO>:secret:dev/ping/client-R3cHbp"
        objectType: "secretsmanager"
        objectAlias: "ping-client"
```


(Optional)
```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: jit-secrets
  namespace: domino-field
spec:
  provider: aws
  parameters:
    objects: |
      - objectName: "arn:aws:secretsmanager:us-west-2:<EKS_ACCOUNT_NO>:secret:dev/domino/jit-kNnySv"
        objectType: "secretsmanager"
        objectAlias: "jit.json"
        jmesPath:
          - path: "root_cert"
            objectAlias: "certificate.cer"
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
  labels:
    app: nginx
spec:
  serviceAccountName: jit
  volumes:
    - name: jit-secrets
      csi:
        driver: secrets-store.csi.k8s.io
        readOnly: true
        volumeAttributes:
          secretProviderClass: "jit-secrets"
  containers:
  - name: nginx
    image: nginx
    volumeMounts:
      - name: jit-secrets
        mountPath: "/etc/config/jit/"
```


3. Verify that the secrets are loaded 
```shell
kubectl -n domino-field exec -it nginx -c nginx -- cat /etc/config/jit/jit.json

###{"root_cert":"test_contents","jit_endpoint":"http://www.google.com","token_endpoint":"http://www.google.com","client_id":"test_client_id","client_secret":"test_client_secret","r_username":"nuid_user","r_password":"nuid_password","minimum_token_validity_required_in_seconds":"60.0"}%  

kubectl -n domino-field exec -it nginx -c nginx -- cat /etc/config/jit/certificate.cer

###test_contents%

```

4. Delete Service Account
```shell
kubectl -n domino-field delete service account jit
```
