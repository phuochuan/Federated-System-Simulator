# Held-out Pareto preflight

{
  "ready" : false,
  "determinismClaimed" : false,
  "currentRuntimeIdentity" : {
    "javaBuildHash" : "fda9679f2f0147106416d9779e40bb3da24e0e00deab3fe94c663dab296ab6df",
    "javaVersion" : "21.0.2",
    "osArch" : "amd64",
    "worker" : {
      "python" : "3.13.0 (tags/v3.13.0:60403a5, Oct  7 2024, 09:38:07) [MSC v.1941 64 bit (AMD64)]",
      "platform" : "Windows-10-10.0.19045-SP0",
      "executionDevice" : "cpu",
      "idempotentCheckpointOperations" : true,
      "torchThreads" : 1,
      "torchInteropThreads" : 4,
      "deterministicAlgorithms" : true,
      "packages" : {
        "torch" : "2.14.1+cpu",
        "numpy" : "2.5.4",
        "scikit-learn" : "1.9.1",
        "simpy" : "4.1.2",
        "fastapi" : "0.143.3",
        "uvicorn" : "0.54.0"
      },
      "sourceHashes" : {
        "__init__.py" : "7d322a4d6bfe7329fcc87a924757295e924534766a54367dae9e5c8569fa46fe",
        "api.py" : "5106828afc59edc5d15443fae70b8ea24001aa9c3fa1db0abb5ed17a5c4a2af4",
        "benchmark.py" : "6c57637ab74544307ac8eecf4a83be6568b7337eef3d5d50b7b369477952a7ba",
        "data.py" : "66942456dbf5b80f3edab79c1ef85a73f662d4052448ff6da825e2c9f04aca95",
        "experiment.py" : "9f98846257bc9f5a10274ad317a6af1ab0af0ae4afea1f9dbc0cd3b69eac1e2d",
        "logging_config.py" : "3e976ed8bc56a35bc59a19fda415a8ca4fa02e8e67bd073c03ff24df7dff1493",
        "methods/__init__.py" : "ef3bcf4a210fce4bc5e1324935d9b3da1bff99733d4462a90307985c39bb8812",
        "methods/fairfedcs/__init__.py" : "d4e5387af54981d3fa047a1daf781d75128f4e64e931750b670f14682c09cd93",
        "methods/fedavg/__init__.py" : "31fe24d605fbec4fdd9b13a44669d3bc974128a94fdb51d9a7f72642f903f3b1",
        "methods/fedavg/algorithm.py" : "1984905fae9127baa0d5e1040c5dd1ce7817211646798d2ff2c8781d43e10b99",
        "methods/fedavgm/__init__.py" : "373080f2c6edbbbc0d49d5c4de18a3718cf6ae9dae56dd71745b209dc178a827",
        "methods/fedlbw/__init__.py" : "ffc5403024a7f509a6dc5b3062324986e7b9a1f1b810e6fedd0e42d2c33e1679",
        "methods/fedlbw/algorithm.py" : "6ab3363e0c276cd0466580a48597f9f1ab1ff5f03a768875bcfcc244e172b9d3",
        "methods/fednova/__init__.py" : "627734f3fd298d5073684c1b7f4aed0b04ae00c5dfef2f58adeb25f8c0dbfb9e",
        "methods/fedprox/__init__.py" : "935bfcf3361d1d151665c40927b1063478e03830eb14adab18637c1ea71be699",
        "methods/longfed/__init__.py" : "8021b9ed7b0b51541cf64c0fa94c2ba15af6f1ff788da4c8ccc2d01427f9b85b",
        "methods/oort/__init__.py" : "613805df27cf84c8f0aa92f3f6aee318d0e581215d098beb3387905dd79aaaef",
        "methods/scaffold/__init__.py" : "47a7cb86a238713447a4a92283df6fd4b5f9f4cc8475ae9e1883c2a3e983b5ca",
        "model.py" : "d1c669d0f5fbdc22f3c40aec73907a50161e50429b8e59c59c43bbb94313a4fe",
        "operations.py" : "68302f2505e1de2e4859cb88c06bbeea3487860ad2e85560aa5c49b85bf9c374",
        "plot.py" : "e7c1ce3a7c405b72f5ae7f66134ccb7512a4f9670020eaa81c6ec6340d6a0cff",
        "research_plot.py" : "a46cebb1a10f57dbb875e5395223e37c0d47138c9adaeac085980176692627cf",
        "simulation.py" : "707632b1acc6042df146c79b6fdee75b57b1e421abc73a34d936efd239a10c82"
      },
      "sourceFilesUnchanged" : true
    },
    "workerTransport" : {
      "requestTimeoutMs" : 1800000,
      "retryDelayMs" : 2000,
      "maxAttempts" : 4,
      "retryMaxDelayMs" : 30000
    }
  },
  "reason" : "E0_MISSING: run E0 on this frozen build before the held-out experiment"
}

No training was started.
