#  Copyright (c) ZenML GmbH 2022. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.

from pipelines.deployment_pipelines.deployment_inference_pipeline import (
    vertex_deployment_inference_pipeline,
)
from pipelines.deployment_pipelines.deployment_training_pipeline import (
    vertex_train_deploy_pipeline,
)


def main(type: str) -> None:
    vertex_train_deploy_pipeline()
    vertex_deployment_inference_pipeline()


if __name__ == "__main__":
    main()