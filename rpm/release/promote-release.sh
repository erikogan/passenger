#!/bin/sh

staging=`readlink STAGING`
live=`readlink LIVE`

pushd STAGING

for dir in {fedora/1{5,4,3},rhel/5}/{x86_64,i386}
do
  echo $dir -------------
  createrepo $PWD/$dir
done

popd

# Swap them (removing the old link prevents creating a link w/in a link)
rm -f LIVE STAGING
ln -sf $staging LIVE
ln -sf $live STAGING

# Backport
rsync -av --progress LIVE/. STAGING/.