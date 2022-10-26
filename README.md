# playground

* Create a directory named ```tmpfs``` on ```/tmp``` directory
  > ```mkdir /tmp/tmpfs```

* Mount tmpfs on every reboot by adding following line in ```/etc/fstab```
  > ```myramdisk /tmp/tmpfs tmpfs defaults,size=512m,x-gvfs-show 0 0```
  
* Run ```server.py```
  > python server.py
