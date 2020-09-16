#!/bin/bash

if [[ -d charts ]]; then 
  ls -la 
else
  echo "No charts directory found" 
  exit 1
fi

# create clean repo cache dir
[[ -d "chart-repo-cache" ]] && rm -rf chart-repo-cache
mkdir chart-repo-cache

# add SKA Helm Repository
helm repo add skatelescope $HELM_HOST/repository/helm-chart --repository-cache chart-repo-cache
helm repo list
helm repo update
helm search repo skatelescope
helm search repo skatelescope >> chart-repo-cache/before

# Package charts
[ -z "$CHARTS_TO_PUBLISH" ] && export CHARTS_TO_PUBLISH=$(cd charts; ls -d */)
for chart in $CHARTS_TO_PUBLISH; do
  echo "######## Packaging $chart #########"
  helm package charts/"$chart" --destination chart-repo-cache
done

# rebuild index
helm repo index chart-repo-cache --merge chart-repo-cache/skatelescope-index.yaml

ls -la chart-repo-cache
echo "cat chart-repo-cache/skatelescope-index.yaml"
cat chart-repo-cache/skatelescope-index.yaml

# check for pre-existing files
for file in $(cd chart-repo-cache; ls *.tgz); do
  echo "Checking if $file is already in index:"
  cat chart-repo-cache/skatelescope-index.yaml | grep "$file" || echo "Not found in index 👍";
done

for file in chart-repo-cache/*.tgz; do
  echo "######### UPLOADING ${file##*/}";
  curl -v -u $HELM_USERNAME:$HELM_PASSWORD --upload-file ${file} $HELM_HOST/repository/helm-chart/${file##*/};
done
curl -v -u $HELM_USERNAME:$HELM_PASSWORD --upload-file chart-repo-cache/index.yaml $HELM_HOST/repository/helm-chart/${file##*/};

helm repo update
helm search repo skatelescope >> chart-repo-cache/after
helm search repo skatelescope

echo "This publishing step brought about the following changes"
diff chart-repo-cache/before chart-repo-cache/after --color

rm -rf chart-repo-cache
