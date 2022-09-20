#!/bin/bash

set -e
python setup.py gen docs
rm -rf /tmp/docs
mv docs/ /tmp/docs
git checkout gh-pages
# there's probably better ways but we know none has spaces
rm -rf $(ls /tmp/docs)
mv /tmp/docs/* .
git add constructors/ types/ methods/ index.html js/search.js css/ img/
git commit --amend -m "Update documentation"
git push --force
git checkout v1
