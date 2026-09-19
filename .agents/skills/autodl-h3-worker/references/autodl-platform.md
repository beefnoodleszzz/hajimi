# AutoDL platform facts used by this skill

These facts were checked in the official AutoDL help site on 2026-09-19.
Reopen the linked pages before relying on details that can change.

## Instance data and local disk

- [Instance data retention](https://autodl.com/docs/instance_data/): instance
  data remains through normal shutdown/start and package expiration. An
  instance released after 15 consecutive powered-off days loses all data.
  System reset or image replacement clears the system disk but preserves
  `/root/autodl-tmp`.
- [Local data disk](https://autodl.com/docs/local_disk/): system/data disks are
  generally local SSD; local data disks have no redundant copies and are not
  covered by an AutoDL reliability guarantee. Keep important light files backed
  up elsewhere.
- [Quick start](https://autodl.com/docs/quick_start/): a running instance starts
  billing; shut down when finished only when the active user task authorizes
  changing instance state.

## File storage

- [File storage](https://autodl.com/docs/fs/): network-shared storage can be
  mounted across instances in the same region at `/root/autodl-fs` after it is
  initialized and attached. It has redundant backend copies but lower IO
  performance than the local data disk. Use it for important code/config and
  copy high-IO workloads to local data disk.
- AutoDL's current page says file storage is cleared after an account has not
  logged in for three consecutive months or has at least ¥50 in arrears. Do not
  describe it as an unconditional permanent archive.

## SSH and transfers

- [SSH](https://autodl.com/docs/ssh/): keyless SSH is configured by adding a
  public key through the AutoDL console. The docs recommend `screen` or `tmux`
  for long-running work so an SSH disconnect does not terminate the process.
- [Upload data](https://autodl.com/docs/scp/): `scp` transfers files and
  directories. The examples run on the local computer and use uppercase `-P`
  for the SSH port. For many small files, the docs suggest a tar stream; Hajimi
  should prefer its existing rsync/scp transport when available.
- [Download data](https://autodl.com/docs/down/): SCP download also runs from
  the local computer; pull only the outputs needed by Hajimi.

## Project operating implications

- Confirm `/root/autodl-fs` is mounted before writing a backup there; the path
  existing by itself is not proof that file storage is attached.
- Do not treat local data-disk survival through a system reset as a backup.
- Do not use AutoDL's shared storage as the live ComfyUI model/inference path
  without an IO test.
- SSH uses the currently configured instance address/port; do not copy the
  examples' sample host or port into project configuration.
