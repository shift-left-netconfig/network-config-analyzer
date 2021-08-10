|query|src_ns|src_pods|dst_ns|dst_pods|connection|
|---|---|---|---|---|---|
|istio-policy1, config: istio-policy1||||||
|||ip block: 0.0.0.0/0|[default]|[app in (special_skydive)]|TCP 1-65536,|
|||ip block: 0.0.0.0/0|[kube-system,vendor-system]|[*]|TCP 1-65536,|
||[default,kube-system,vendor-system]|[*]|[default]|[app in (special_skydive)]|TCP 1-65536,|
||[default,kube-system,vendor-system]|[*]|[kube-system,vendor-system]|[*]|TCP 1-65536,|
|||ip block: 1.2.3.0/24|[default]|[app in (skydive)]|TCP 26257,|
||[default,vendor-system]|[*]|[default]|[*]|TCP 26257,|


|query|src_ns|src_pods|dst_ns|dst_pods|connection|
|---|---|---|---|---|---|
|istio-policy2, config: istio-policy2||||||
|||ip block: 1.2.3.0/24|[default]|[app in (skydive)]|TCP 30,50,|
|||ip block: 2.2.2.2/32|[default]|[app in (skydive)]|TCP 30,50,|
||[default,kube-system]|[*]|[default]|[app in (skydive)]|TCP 30,50,|
||[default]|[app in (special_skydive)]|[default]|[*]|TCP 30,50,|

