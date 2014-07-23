# Copyright 2012 Grid Dynamics
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import abc
import contextlib
import os

import six
import time

from oslo.config import cfg

from nova import exception
from nova.openstack.common import excutils
from nova.openstack.common import fileutils
from nova.openstack.common.gettextutils import _
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import units
from nova import utils
from nova.virt.disk import api as disk
from nova.virt import images
from nova.virt.libvirt import config as vconfig
# from nova.virt.libvirt import rbd_utils
import rbd_utils
from nova.virt.libvirt import utils as libvirt_utils

__imagebackend_opts = [
    cfg.StrOpt('images_type',
               default='default',
               help='VM Images format. Acceptable values are: raw, qcow2, lvm,'
                    ' rbd, default. If default is specified,'
                    ' then use_cow_images flag is used instead of this one.',
               deprecated_group='DEFAULT',
               deprecated_name='libvirt_images_type'),
    cfg.StrOpt('images_volume_group',
               help='LVM Volume Group that is used for VM images, when you'
                    ' specify images_type=lvm.',
               deprecated_group='DEFAULT',
               deprecated_name='libvirt_images_volume_group'),
    cfg.BoolOpt('sparse_logical_volumes',
                default=False,
                help='Create sparse logical volumes (with virtualsize)'
                     ' if this flag is set to True.',
                deprecated_group='DEFAULT',
                deprecated_name='libvirt_sparse_logical_volumes'),
    cfg.StrOpt('volume_clear',
               default='zero',
               help='Method used to wipe old volumes (valid options are: '
                    'none, zero, shred)'),
    cfg.IntOpt('volume_clear_size',
               default=0,
               help='Size in MiB to wipe at start of old volumes. 0 => all'),
    cfg.StrOpt('images_rbd_pool',
               default='rbd',
               help='The RADOS pool in which rbd volumes are stored',
               deprecated_group='DEFAULT',
               deprecated_name='libvirt_images_rbd_pool'),
    cfg.StrOpt('images_rbd_ceph_conf',
               default='',  # default determined by librados
               help='Path to the ceph configuration file to use',
               deprecated_group='DEFAULT',
               deprecated_name='libvirt_images_rbd_ceph_conf'),
        ]

CONF = cfg.CONF
CONF.register_opts(__imagebackend_opts, 'libvirt')
CONF.import_opt('image_cache_subdirectory_name', 'nova.virt.imagecache')
CONF.import_opt('preallocate_images', 'nova.virt.driver')
CONF.import_opt('rbd_user', 'nova.virt.libvirt.volume', group='libvirt')
CONF.import_opt('rbd_secret_uuid', 'nova.virt.libvirt.volume', group='libvirt')

LOG = logging.getLogger(__name__)


# CCC@six.add_metaclass(abc.ABCMeta)
class Image(object):

    def __init__(self, source_type, driver_format, is_block_dev=False):
        """Image initialization.

        :source_type: block or file
        :driver_format: raw or qcow2
        :is_block_dev:
        """
        self.source_type = source_type
        self.driver_format = driver_format
        self.is_block_dev = is_block_dev
        self.preallocate = False

        # NOTE(dripton): We store lines of json (path, disk_format) in this
        # file, for some image types, to prevent attacks based on changing the
        # disk_format.
        self.disk_info_path = None

        # NOTE(mikal): We need a lock directory which is shared along with
        # instance files, to cover the scenario where multiple compute nodes
        # are trying to create a base file at the same time
        self.lock_path = os.path.join(CONF.instances_path, 'locks')

    @abc.abstractmethod
    def create_image(self, prepare_template, base, size, *args, **kwargs):
        """Create image from template.

        Contains specific behavior for each image type.

        :prepare_template: function, that creates template.
        Should accept `target` argument.
        :base: Template name
        :size: Size of created image in bytes
        """
        pass

    def libvirt_info(self, disk_bus, disk_dev, device_type, cache_mode,
            extra_specs, hypervisor_version):
        """Get `LibvirtConfigGuestDisk` filled for this image.

        :disk_dev: Disk bus device name
        :disk_bus: Disk bus type
        :device_type: Device type for this image.
        :cache_mode: Caching mode for this image
        :extra_specs: Instance type extra specs dict.
        """
        info = vconfig.LibvirtConfigGuestDisk()
        info.source_type = self.source_type
        info.source_device = device_type
        info.target_bus = disk_bus
        info.target_dev = disk_dev
        info.driver_cache = cache_mode
        info.driver_format = self.driver_format
        driver_name = libvirt_utils.pick_disk_driver_name(hypervisor_version,
                                                          self.is_block_dev)
        info.driver_name = driver_name
        info.source_path = self.path

        tune_items = ['disk_read_bytes_sec', 'disk_read_iops_sec',
            'disk_write_bytes_sec', 'disk_write_iops_sec',
            'disk_total_bytes_sec', 'disk_total_iops_sec']
        # Note(yaguang): Currently, the only tuning available is Block I/O
        # throttling for qemu.
        if self.source_type in ['file', 'block']:
            for key, value in extra_specs.iteritems():
                scope = key.split(':')
                if len(scope) > 1 and scope[0] == 'quota':
                    if scope[1] in tune_items:
                        setattr(info, scope[1], value)
        return info

    def check_image_exists(self):
        return os.path.exists(self.path)

    def cache(self, fetch_func, filename, size=None, *args, **kwargs):
        """Creates image from template.

        Ensures that template and image not already exists.
        Ensures that base directory exists.
        Synchronizes on template fetching.

        :fetch_func: Function that creates the base image
                     Should accept `target` argument.
        :filename: Name of the file in the image directory
        :size: Size of created image in bytes (optional)
        """
        print("*L*: cache rbd name = %s" % self.rbd_name)
        print("*L*: cache filename = %s" % filename)
        self.check_image_exists()
        print("*L*: ---")
        time.sleep(2)

        self.check_image_exists()
        print("*L*: ---")
        time.sleep(2)
        
        self.check_image_exists()
        print("*L*: ---")
        time.sleep(2)
        print("*L*: continuing..")
        time.sleep(200)
        
        @utils.synchronized(filename, external=True, lock_path=self.lock_path)
        def fetch_func_sync(target, *args, **kwargs):
            fetch_func(target=target, *args, **kwargs)

        base_dir = os.path.join(CONF.instances_path,
                                CONF.image_cache_subdirectory_name)
        if not os.path.exists(base_dir):
            fileutils.ensure_tree(base_dir)
        base = os.path.join(base_dir, filename)

        if not self.check_image_exists() or not os.path.exists(base):
            self.create_image(fetch_func_sync, base, size,
                              *args, **kwargs)

        if (size and self.preallocate and self._can_fallocate() and
                os.access(self.path, os.W_OK)):
            utils.execute('fallocate', '-n', '-l', size, self.path)

    def _can_fallocate(self):
        """Check once per class, whether fallocate(1) is available,
           and that the instances directory supports fallocate(2).
        """
        can_fallocate = getattr(self.__class__, 'can_fallocate', None)
        if can_fallocate is None:
            _out, err = utils.trycmd('fallocate', '-n', '-l', '1',
                                     self.path + '.fallocate_test')
            fileutils.delete_if_exists(self.path + '.fallocate_test')
            can_fallocate = not err
            self.__class__.can_fallocate = can_fallocate
            if not can_fallocate:
                LOG.error(_('Unable to preallocate_images=%(imgs)s at path: '
                            '%(path)s'), {'imgs': CONF.preallocate_images,
                                           'path': self.path})
        return can_fallocate

    def verify_base_size(self, base, size, base_size=0):
        """Check that the base image is not larger than size.
           Since images can't be generally shrunk, enforce this
           constraint taking account of virtual image size.
        """

        # Note(pbrady): The size and min_disk parameters of a glance
        #  image are checked against the instance size before the image
        #  is even downloaded from glance, but currently min_disk is
        #  adjustable and doesn't currently account for virtual disk size,
        #  so we need this extra check here.
        # NOTE(cfb): Having a flavor that sets the root size to 0 and having
        #  nova effectively ignore that size and use the size of the
        #  image is considered a feature at this time, not a bug.

        if size is None:
            return

        if size and not base_size:
            base_size = self.get_disk_size(base)

        if size < base_size:
            msg = _('%(base)s virtual size %(base_size)s '
                    'larger than flavor root disk size %(size)s')
            LOG.error(msg % {'base': base,
                              'base_size': base_size,
                              'size': size})
            raise exception.FlavorDiskTooSmall()

    def get_disk_size(self, name):
        disk.get_disk_size(name)

    def snapshot_extract(self, target, out_format):
        raise NotImplementedError()

    def _get_driver_format(self):
        return self.driver_format

    def resolve_driver_format(self):
        """Return the driver format for self.path.

        First checks self.disk_info_path for an entry.
        If it's not there, calls self._get_driver_format(), and then
        stores the result in self.disk_info_path

        See https://bugs.launchpad.net/nova/+bug/1221190
        """
        def _dict_from_line(line):
            if not line:
                return {}
            try:
                return jsonutils.loads(line)
            except (TypeError, ValueError) as e:
                msg = (_("Could not load line %(line)s, got error "
                        "%(error)s") %
                        {'line': line, 'error': unicode(e)})
                raise exception.InvalidDiskInfo(reason=msg)

        @utils.synchronized(self.disk_info_path, external=False,
                            lock_path=self.lock_path)
        def write_to_disk_info_file():
            # Use os.open to create it without group or world write permission.
            fd = os.open(self.disk_info_path, os.O_RDWR | os.O_CREAT, 0o644)
            with os.fdopen(fd, "r+") as disk_info_file:
                line = disk_info_file.read().rstrip()
                dct = _dict_from_line(line)
                if self.path in dct:
                    msg = _("Attempted overwrite of an existing value.")
                    raise exception.InvalidDiskInfo(reason=msg)
                dct.update({self.path: driver_format})
                disk_info_file.seek(0)
                disk_info_file.truncate()
                disk_info_file.write('%s\n' % jsonutils.dumps(dct))
            # Ensure the file is always owned by the nova user so qemu can't
            # write it.
            utils.chown(self.disk_info_path, owner_uid=os.getuid())

        try:
            if (self.disk_info_path is not None and
                        os.path.exists(self.disk_info_path)):
                with open(self.disk_info_path) as disk_info_file:
                    line = disk_info_file.read().rstrip()
                    dct = _dict_from_line(line)
                    for path, driver_format in dct.iteritems():
                        if path == self.path:
                            return driver_format
            driver_format = self._get_driver_format()
            if self.disk_info_path is not None:
                fileutils.ensure_tree(os.path.dirname(self.disk_info_path))
                write_to_disk_info_file()
        except OSError as e:
            raise exception.DiskInfoReadWriteFail(reason=unicode(e))
        return driver_format

    @staticmethod
    def is_shared_block_storage():
        '''Return True if the backend puts images on a shared block storage
        '''
        return False

    def direct_fetch(self, image_id, image_meta, image_locations):
        """Create an image from a direct image location.

        :raises: exception.ImageUnacceptable if it cannot be fetched directly
        """
        reason = _('direct_fetch() is not implemented')
        raise exception.ImageUnacceptable(image_id=image_id, reason=reason)

class Rbd(Image):
    def __init__(self, instance=None, disk_name=None, path=None, **kwargs):
        super(Rbd, self).__init__("block", "rbd", is_block_dev=True)
        if path:
            try:
                self.rbd_name = path.split('/')[1]
            except IndexError:
                raise exception.InvalidDevicePath(path=path)
        else:
            # self.rbd_name = '%s_%s' % (instance['uuid'], disk_name)
            self.rbd_name = '%s_%s' % (instance, disk_name)
        


        if not CONF.libvirt.images_rbd_pool:
            raise RuntimeError(_('You should specify'
                                 ' images_rbd_pool'
                                 ' flag to use rbd images.'))
        # CONF.libvirt.rbd_secret_uuid
        #print(CONF.libvirt.images_rbd_pool)
        #CONF.libvirt.images_rbd_pool = 'vm-images'
        #CONF.libvirt.rbd_user = 'compute01'
        #CONF.libvirt.images_rbd_ceph_conf='/etc/ceph/ceph.conf'
        
        self.pool = CONF.libvirt.images_rbd_pool
        self.rbd_user = CONF.libvirt.rbd_user
        self.ceph_conf = CONF.libvirt.images_rbd_ceph_conf
        
        print("Rbd pool:%s" % self.pool)
        print("Rbd user:%s" % self.rbd_user)


        self.driver = rbd_utils.RBDDriver(
            pool=self.pool,
            ceph_conf=self.ceph_conf,
            rbd_user=self.rbd_user,
            rbd_lib=kwargs.get('rbd'),
            rados_lib=kwargs.get('rados'))

        self.path = 'rbd:%s/%s' % (self.pool, self.rbd_name)
        if self.rbd_user:
            self.path += ':id=' + self.rbd_user
        if self.ceph_conf:
            self.path += ':conf=' + self.ceph_conf

    def libvirt_info(self, disk_bus, disk_dev, device_type, cache_mode,
            extra_specs, hypervisor_version):
        """Get `LibvirtConfigGuestDisk` filled for this image.

        :disk_dev: Disk bus device name
        :disk_bus: Disk bus type
        :device_type: Device type for this image.
        :cache_mode: Caching mode for this image
        :extra_specs: Instance type extra specs dict.
        """
        info = vconfig.LibvirtConfigGuestDisk()

        hosts, ports = self.driver.get_mon_addrs()
        info.source_device = device_type
        info.driver_format = 'raw'
        info.driver_cache = cache_mode
        info.target_bus = disk_bus
        info.target_dev = disk_dev
        info.source_type = 'network'
        info.source_protocol = 'rbd'
        info.source_name = '%s/%s' % (self.pool, self.rbd_name)
        info.source_hosts = hosts
        info.source_ports = ports
        auth_enabled = (CONF.libvirt.rbd_user is not None)
        if CONF.libvirt.rbd_secret_uuid:
            info.auth_secret_uuid = CONF.libvirt.rbd_secret_uuid
            auth_enabled = True  # Force authentication locally
            if CONF.libvirt.rbd_user:
                info.auth_username = CONF.libvirt.rbd_user
        if auth_enabled:
            info.auth_secret_type = 'ceph'
            info.auth_secret_uuid = CONF.libvirt.rbd_secret_uuid
        return info

    def _can_fallocate(self):
        return False

    def check_image_exists(self):
        return self.driver.exists(self.rbd_name)

    def get_disk_size(self, name):
        """Returns the size of the virtual disk in bytes.

        The name argument is ignored since this backend already knows
        its name, and callers may pass a non-existent local file path.
        """
        return self.driver.size(self.rbd_name)

    def create_image(self, prepare_template, base, size, *args, **kwargs):

        if not self.check_image_exists():
            prepare_template(target=base, max_size=size, *args, **kwargs)
        else:
            self.verify_base_size(base, size)

        # prepare_template() may have cloned the image into a new rbd
        # image already instead of downloading it locally
        if not self.check_image_exists():
            # keep using the command line import instead of librbd since it
            # detects zeroes to preserve sparseness in the image
            args = ['--pool', self.pool, base, self.rbd_name]
            if self.driver.supports_layering():
                args += ['--new-format']
                args += self.driver.ceph_args()
                utils.execute('rbd', 'import', *args)

        if size and size > self.get_disk_size(self.rbd_name):
            self.driver.resize(self.rbd_name, size)

    def snapshot_extract(self, target, out_format):
        images.convert_image(self.path, target, out_format)

    @staticmethod
    def is_shared_block_storage():
        return True

    def direct_fetch(self, image_id, image_meta, image_locations):
        if self.check_image_exists():
            return
        if image_meta.get('disk_format') not in ['raw', 'iso']:
            reason = _('Image is not raw format')
            raise exception.ImageUnacceptable(image_id=image_id, reason=reason)
        if not self.driver.supports_layering():
            reason = _('installed version of librbd does not support cloning')
            raise exception.ImageUnacceptable(image_id=image_id, reason=reason)

        for location in image_locations:
            if self.driver.is_cloneable(location, image_meta):
                return self.driver.clone(location, self.rbd_name)

        reason = _('No image locations are accessible')
        raise exception.ImageUnacceptable(image_id=image_id, reason=reason)


class Backend(object):
    def __init__(self, use_cow):
        self.BACKEND = {
#            'raw': Raw,
#            'qcow2': Qcow2,
#            'lvm': Lvm,
            'rbd': Rbd
#            'default': Qcow2 if use_cow else Raw
        }

    def backend(self, image_type=None):
        if not image_type:
            image_type = CONF.libvirt.images_type
        image = self.BACKEND.get(image_type)
        if not image:
            raise RuntimeError(_('Unknown image_type=%s') % image_type)
        return image

    def image(self, instance, disk_name, image_type=None):
        """Constructs image for selected backend

        :instance: Instance name.
        :name: Image name.
        :image_type: Image type.
        Optional, is CONF.libvirt.images_type by default.
        """
        backend = self.backend(image_type)
        return backend(instance=instance, disk_name=disk_name)

    def snapshot(self, disk_path, image_type=None):
        """Returns snapshot for given image

        :path: path to image
        :image_type: type of image
        """
        backend = self.backend(image_type)
        return backend(path=disk_path)


    
    