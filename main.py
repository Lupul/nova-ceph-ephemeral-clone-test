import sys
import time
from nova import config

from nova.virt.libvirt import utils as libvirt_utils
from oslo.config import cfg

import imagebackend
from imagebackend import Rbd as Rbd_local

CONF = cfg.CONF


def image(instance,fname, image_type='rbd'):
    image_backend = imagebackend.Backend(False)
    return image_backend.image(instance, fname, image_type)


def main():
    config.parse_args(sys.argv)

    print("backend ==================")
    backend = image('8bee4eaf-616c-4f22-bce4-b64dec1d402bxx', 'disk', image_type='rbd')
    print("backend.check_image_exists %s " % backend.check_image_exists())      # --- never faults  ---
    time.sleep(2)
    print("backend.check_image_exists %s " % backend.check_image_exists())      # --- segfaults here  ---
    time.sleep(2)
    print("backend.check_image_exists %s " % backend.check_image_exists())      # --- segfaults here  ---
    time.sleep(2)
    print("backend.check_image_exists %s " % backend.check_image_exists())      # --- segfaults here  ---
    time.sleep(2)

    backend.cache(fetch_func=libvirt_utils.fetch_image,
                          filename='cfcaebe8ba27540d44595ba1c5bd69a6360a2189',
                          size=1024,
                          backend=backend)
    # --- segfault ---
    
    
    print("\nrbd_drv0 ==================")      # --- passes OK ---
    rbd_drv0 = Rbd_local(instance='8bee4eaf-616c-4f22-bce4-b64dec1d402b', disk_name='disk')
    print( rbd_drv0.driver.get_pool_info() )
    print( rbd_drv0.check_image_exists() )
    print( rbd_drv0.check_image_exists() )
    print( rbd_drv0.check_image_exists() )
    print( rbd_drv0.driver.get_pool_info() )

    print("\nrbd_drv ==================")       # --- passes OK ---
    rbd_drv = Rbd_local(instance='8bee4eaf-616c-4f22-bce4-b64dec1d402bXXX', disk_name='disk')
    print( rbd_drv.driver.get_pool_info() )
    print( rbd_drv.check_image_exists() )
    print( rbd_drv.check_image_exists() )
    print( rbd_drv.check_image_exists() )
    print( rbd_drv.driver.get_pool_info() )


if __name__ == "__main__":
    main()
