{{/*
Expand the name of the chart.
*/}}
{{- define "nosqlbench-demo.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "nosqlbench-demo.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "nosqlbench-demo.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "nosqlbench-demo.labels" -}}
helm.sh/chart: {{ include "nosqlbench-demo.chart" . }}
{{ include "nosqlbench-demo.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "nosqlbench-demo.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nosqlbench-demo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "nosqlbench-demo.serviceAccountName" -}}
{{- if .Values.rbac.create }}
{{- include "nosqlbench-demo.fullname" . }}
{{- else }}
{{- default "default" }}
{{- end }}
{{- end }}

{{/*
Create the webapp image name
*/}}
{{- define "nosqlbench-demo.webapp.image" -}}
{{- $registry := .Values.global.imageRegistry | default .Values.webapp.image.registry -}}
{{- $repository := .Values.webapp.image.repository -}}
{{- $tag := .Values.webapp.image.tag | default .Chart.AppVersion -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Create the nosqlbench image name
*/}}
{{- define "nosqlbench-demo.nosqlbench.image" -}}
{{- $registry := .Values.global.imageRegistry | default .Values.nosqlbench.image.registry -}}
{{- $repository := .Values.nosqlbench.image.repository -}}
{{- $tag := .Values.nosqlbench.image.tag -}}
{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end }}

{{/*
Generate database configuration as environment variables
*/}}
{{- define "nosqlbench-demo.databaseEnv" -}}
{{- if .Values.databases.cassandra.enabled }}
- name: CASSANDRA_HOST
  value: {{ .Values.databases.cassandra.host | quote }}
- name: CASSANDRA_PORT
  value: {{ .Values.databases.cassandra.port | quote }}
- name: CASSANDRA_LOCALDC
  value: {{ .Values.databases.cassandra.localdc | quote }}
{{- if .Values.databases.cassandra.username }}
- name: CASSANDRA_USERNAME
  value: {{ .Values.databases.cassandra.username | quote }}
{{- end }}
{{- if .Values.databases.cassandra.password }}
- name: CASSANDRA_PASSWORD
  value: {{ .Values.databases.cassandra.password | quote }}
{{- end }}
{{- end }}
{{- if .Values.databases.opensearch.enabled }}
- name: OPENSEARCH_HOST
  value: {{ .Values.databases.opensearch.host | quote }}
- name: OPENSEARCH_PORT
  value: {{ .Values.databases.opensearch.port | quote }}
{{- if .Values.databases.opensearch.username }}
- name: OPENSEARCH_USERNAME
  value: {{ .Values.databases.opensearch.username | quote }}
{{- end }}
{{- if .Values.databases.opensearch.password }}
- name: OPENSEARCH_PASSWORD
  value: {{ .Values.databases.opensearch.password | quote }}
{{- end }}
{{- end }}
{{- if .Values.databases.presto.enabled }}
- name: PRESTO_HOST
  value: {{ .Values.databases.presto.host | quote }}
- name: PRESTO_PORT
  value: {{ .Values.databases.presto.port | quote }}
- name: PRESTO_USER
  value: {{ .Values.databases.presto.user | quote }}
- name: PRESTO_CATALOG
  value: {{ .Values.databases.presto.catalog | quote }}
{{- end }}
- name: METRICS_ENDPOINT
  value: {{ .Values.metrics.endpoint | quote }}
{{- end }}

{{/*
Generate enabled databases list
*/}}
{{- define "nosqlbench-demo.enabledDatabases" -}}
{{- $databases := list -}}
{{- if .Values.databases.cassandra.enabled -}}
{{- $databases = append $databases "cassandra" -}}
{{- end -}}
{{- if .Values.databases.opensearch.enabled -}}
{{- $databases = append $databases "opensearch" -}}
{{- end -}}
{{- if .Values.databases.presto.enabled -}}
{{- $databases = append $databases "presto" -}}
{{- end -}}
{{- join "," $databases -}}
{{- end }}

{{/*
Generate workload list based on enabled databases
*/}}
{{- define "nosqlbench-demo.availableWorkloads" -}}
{{- $workloads := list -}}
{{- if .Values.databases.cassandra.enabled -}}
{{- $workloads = append $workloads "cassandra_sai" -}}
{{- $workloads = append $workloads "cassandra_lwt" -}}
{{- end -}}
{{- if .Values.databases.opensearch.enabled -}}
{{- $workloads = append $workloads "opensearch_basic" -}}
{{- $workloads = append $workloads "opensearch_vector" -}}
{{- $workloads = append $workloads "opensearch_bulk" -}}
{{- end -}}
{{- if .Values.databases.presto.enabled -}}
{{- $workloads = append $workloads "presto_analytics" -}}
{{- $workloads = append $workloads "presto_ecommerce" -}}
{{- end -}}
{{- join "," $workloads -}}
{{- end }}

{{/*
Generate job name for workload and phase
*/}}
{{- define "nosqlbench-demo.jobName" -}}
{{- $workload := .workload -}}
{{- $phase := .phase -}}
{{- $fullname := include "nosqlbench-demo.fullname" .context -}}
{{- printf "%s-%s-%s" $fullname $workload $phase | trunc 63 | trimSuffix "-" -}}
{{- end }}
