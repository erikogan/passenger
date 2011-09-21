#!/bin/sh

staging=`readlink STAGING`
live=`readlink LIVE`

dirname=`dirname $0`
# This will only work on linux, but for now that's ok, it is more important it work with a relative path
symlinks=`readlink -f $dirname`/sl_symlinks.rb

pushd STAGING

$symlinks

for dir in {fedora/1{5,4},rhel/{5,6}}/{x86_64,i386}
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