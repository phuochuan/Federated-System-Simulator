# Federated System Simulator

MiniFLS is a planned resource-aware federated learning research testbed using Java Spring Boot, Python/PyTorch, and SimPy.

The target architecture coordinates 100 logical clients with one active local training job at a time. The initial milestone is a reproducible 20-round FedAvg pipeline on Covertype; resource simulation, FedLBW, and resource-aware selection follow afterward.

## Current state

This repository currently contains the initial Spring Boot scaffold in `ferderatedsystem/`. Federated training and simulation are not implemented yet.

## Java project

The scaffold specifies Java 25 and uses the included Gradle wrapper.

```powershell
cd ferderatedsystem
.\gradlew.bat test
.\gradlew.bat bootRun
```

Generated builds, IDE settings, local environment files, datasets, and experiment artifacts are excluded from Git.
