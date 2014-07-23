**Branch test-ok**

python ./imagebackend.py

```Shell
default
Rbd pool:vm-images
Rbd user:compute01
RBDDriver pool:vm-images
RBDDriver user:compute01
{'total': 2799219187712L, 'used': 391773302784L, 'free': 2407445884928L}
*L*  RBDVolumeProxy __init__ end
*L*  RBDVolumeProxy __enter__
*L*  RBDVolumeProxy __exit__
True
*L*  RBDVolumeProxy __init__ end
*L*  RBDVolumeProxy __enter__
*L*  RBDVolumeProxy __exit__
True
*L*  RBDVolumeProxy __init__ end
*L*  RBDVolumeProxy __enter__
*L*  RBDVolumeProxy __exit__
True
*L*  RBDVolumeProxy __init__ end
*L*  RBDVolumeProxy __enter__
*L*  RBDVolumeProxy __exit__
True
*L*  RBDVolumeProxy __init__ end
*L*  RBDVolumeProxy __enter__
*L*  RBDVolumeProxy __exit__
True
{'total': 2799219187712L, 'used': 391773302784L, 'free': 2407445884928L}
Rbd pool:vm-images
Rbd user:compute01
RBDDriver pool:vm-images
RBDDriver user:compute01
{'total': 2799219187712L, 'used': 391773302784L, 'free': 2407445884928L}
False
False
False
False
False
{'total': 2799219187712L, 'used': 391773282304L, 'free': 2407445905408L}
```

**Branch test-fault**

python main.py --config-file=/etc/nova/nova.conf --config-file=/etc/nova/nova-compute.conf

```Shell
backend ==================
Rbd pool:vm-images
Rbd user:compute01
backend.check_image_exists False 
*L*: cache rbd name = 8bee4eaf-616c-4f22-bce4-b64dec1d402bxx_disk
*L*: cache filename = cfcaebe8ba27540d44595ba1c5bd69a6360a2189
*L*: ---
Segmentation fault
```
