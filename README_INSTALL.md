
# JIT Installation Instructions

Follow these set of instructions to install JIT

## On the Domino Side Create the Tar balls 

1. Create JIT Client Tarball

We will define a project root folder as `$PROJECT_BASE_FLDR` all folders below are with respect to
this base folder

```shell
cd $PROJECT_BASE_FLDR
export image_name=jit-client
export image_tag=v1.0.0-release 
docker build -f ./JITClientDockerfile -t $image_name:$image_tag .
docker images | grep jit-client
export image_id=2dd0fb322ebb
rm -rf ./install/client/*
docker save -o ./install/client/jit-client.tar $image_id $image_name:$image_tag
tar -cvpzf jit_install/jit_client.tar.gz ./install/client
```

2. Create JIT Server Tarball

For Mock JIT Server use the one below
```shell
cd $PROJECT_BASE_FLDR
export image_name=mock-jit-server
export image_tag=v1.0.0-release 
docker build -f ./MockJITServerDockerfile -t $image_name:$image_tag .
docker images | grep jit-server
export image_id=#TBD
rm  ./install/server/* 
docker save -o ./install/server/jit-server.tar $image_id $image_name:$image_tag
tar -cvpzf jit_install/jit_server.tar.gz ./install/server
```
For  the actual JIT server use the one below
```shell
cd $PROJECT_BASE_FLDR
export image_name=jit-server
export image_tag=v1.0.0-release 
docker build -f ./JITServerDockerfile -t $image_name:$image_tag .
docker images | grep jit-server
export image_id=#TBD 
rm  ./install/server/* 
docker save -o ./install/server/jit-server.tar $image_id $image_name:$image_tag
tar -cvpzf jit_install/jit_server.tar.gz ./install/server
```

## Push Images from Tarball to Docker Registry

  
1. Push the `jit-client` image
```shell
cd $PROJECT_BASE_FLDR
cd jit_install
rm -rf client
mkdir client
mv jit_client.tar.gz ./client
cd client
gunzip jit_client.tar.gz
tar -xvf jit_client.tar 
rm  jit_client.tar*

export docker_registry=quay.io/domino
export image_name=jit-client
export image_tag=v1.0.0-release 
docker load < ./install/client/jit-client.tar 
docker tag $image_name:$image_tag $docker_registry/$image_name:$image_tag
docker push $docker_registry/$image_name:$image_tag
```

2. Push the `jit-server` image
```shell
cd $PROJECT_BASE_FLDR
cd jit_install
rm -rf server
mkdir server
mv jit_server.tar.gz ./server
cd server 
gunzip jit_server.tar.gz
tar -xvf jit_server.tar 
rm  jit_server.tar*

export docker_registry=quay.io/domino
export image_name=jit-server
export image_tag=v1.0.0-release 
docker load < ./install/server/jit-server.tar 
docker tag $image_name:$image_tag $docker_registry/$image_name:$image_tag
docker push $docker_registry/$image_name:$image_tag
```


## Install JIT

1. Create a namespace `domino-field` in which this service will be installed

2. Open the file `./helm/jit/values.yaml`
And change the value for `<EKS_ACCOUNT_NO>`
```yaml
image:
  repository: quay.io/domino
  serverContainer: jit-server
  clientContainer: jit-client
  serverAppVersion: v1.0.0-release
  clientAppVersion: v1.0.0-release
  pullPolicy: Always

env:
  name: jit
  service: jit-svc
  iamrole: arn:aws:iam::<EKS_ACCOUNT_NO>:role/dev-domino-jit-role
  namespace:
    platform: domino-platform
    compute: domino-compute
    field: domino-field


```

## Helm Install

For helm installation run 
```shell
helm install -f ./helm/jit/values.yaml jit helm/jit -n domino-field
```

For helm updates run 
```shell
helm upgrade -f ./helm/jit/values.yaml jit helm/jit -n domino-field
```

For helm delete run
```shell
helm delete jit -n domino-field
```

## Inside the Workspace

You should look for environment variables
```properties
AWS_SHARED_CREDENTIALS_FILE
DOMINO_JIT_ENDPOINT
DOMINO_JIT_REFRESH_ENDPOINT
```
Look inside the file `AWS_SHARED_CREDENTIALS_FILE` for credentials associated with your JIT Session

Lastly if you create new JIT sessions when your workspace is running, update the above file by running

```shell
curl $DOMINO_JIT_REFRESH_ENDPOINT
```

## Debugging errors

You can access the JIT client (runs in a side-car container) logs in the workspace by viewing the file

```shell
/var/log/jit/app.log
```