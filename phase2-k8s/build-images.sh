#!/usr/bin/env bash
set -e

# Redirect Docker CLI to minikube's internal Docker daemon.
# Images built here are available to Kubernetes without a registry.
eval $(minikube docker-env)

docker build -f ../phase2/Dockerfile.server -t server:latest ../phase2
docker build -f ../phase2/Dockerfile.client -t client:latest ../phase2

echo "Images built inside minikube's Docker daemon."
