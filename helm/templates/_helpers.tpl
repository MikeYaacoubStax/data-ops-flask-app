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
Database configuration is handled dynamically through the web UI
No static database helpers needed
*/}}

{{/*
Generate job name for workload and phase
*/}}
{{- define "nosqlbench-demo.jobName" -}}
{{- $workload := .workload -}}
{{- $phase := .phase -}}
{{- $fullname := include "nosqlbench-demo.fullname" .context -}}
{{- printf "%s-%s-%s" $fullname $workload $phase | trunc 63 | trimSuffix "-" -}}
{{- end }}
