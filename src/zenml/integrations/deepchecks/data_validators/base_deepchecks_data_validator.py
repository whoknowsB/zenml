#  Copyright (c) ZenML GmbH 2023. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
"""Base class definition for Deepchecks data validators."""

from abc import ABC, abstractmethod
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    cast,
)

from deepchecks import BaseSuite
from deepchecks.core.checks import BaseCheck
from deepchecks.core.suite import SuiteResult

# not part of deepchecks.tabular.checks
from zenml.data_validators import BaseDataValidator
from zenml.data_validators.base_data_validator import BaseDataValidatorFlavor
from zenml.environment import Environment
from zenml.integrations.deepchecks.enums import DeepchecksModuleName
from zenml.integrations.deepchecks.flavors.deepchecks_tabular_data_validator_flavor import (
    DeepchecksTabularDataValidatorFlavor,
)
from zenml.integrations.deepchecks.validation_checks.base_validation_checks import (
    BaseDeepchecksValidationCheck,
    DeepchecksDataDriftCheck,
    DeepchecksDataValidationCheck,
    DeepchecksModelDriftCheck,
    DeepchecksModelValidationCheck,
)
from zenml.logger import get_logger
from zenml.steps import STEP_ENVIRONMENT_NAME, StepEnvironment
from zenml.utils.string_utils import random_str

logger = get_logger(__name__)


class BaseDeepchecksDataValidator(BaseDataValidator, ABC):
    """Base class for Deepchecks data validators."""

    # We need to set some flavor here, otherwise `get_active_data_validator`
    # will fail. Since the tabular flavor is the flavor has the fewest
    # dependencies, we use it here.
    FLAVOR: ClassVar[
        Type[BaseDataValidatorFlavor]
    ] = DeepchecksTabularDataValidatorFlavor

    @property
    @abstractmethod
    def deepchecks_module(self) -> DeepchecksModuleName:
        """Return the Deepchecks module related to this data validator.

        E.g., `tabular` if the data validator is for tabular data.

        Currently, only `tabular` and `vision` are supported.

        Returns:
            The Deepchecks module related to this data validator.
        """

    @property
    @abstractmethod
    def supported_dataset_types(self) -> Tuple[Type[Any]]:
        """Return the supported dataset types.

        Returns:
            The supported dataset types.
        """

    @property
    @abstractmethod
    def supported_model_types(self) -> Tuple[Type[Any]]:
        """Return the supported model types.

        Returns:
            The supported model types.
        """

    @property
    @abstractmethod
    def dataset_class(self) -> Type[Any]:
        """Return the Deepchecks dataset class.

        Returns:
            The Deepchecks dataset class.
        """

    @property
    @abstractmethod
    def suite_class(self) -> Type[BaseSuite]:
        """Return the Deepchecks suite class.

        Returns:
            The Deepchecks suite class.
        """

    @property
    @abstractmethod
    def full_suite(self) -> BaseSuite:
        """Return the full Deepchecks suite.

        This suite is used by default if no custom list of checks is provided.

        Returns:
            The full Deepchecks suite.
        """

    @property
    @abstractmethod
    def data_validation_check_enum(
        self,
    ) -> Type["DeepchecksDataValidationCheck"]:
        """Return the enum class that contains the data validation checks.

        Returns:
            The enum class that contains the data validation checks.
        """

    @property
    @abstractmethod
    def data_drift_check_enum(self) -> Type["DeepchecksDataDriftCheck"]:
        """Return the enum class that contains the data drift checks.

        Returns:
            The enum class that contains the data drift checks.
        """

    @property
    @abstractmethod
    def model_validation_check_enum(
        self,
    ) -> Type["DeepchecksModelValidationCheck"]:
        """Return the enum class that contains the model validation checks.

        Returns:
            The enum class that contains the model validation checks.
        """

    @property
    @abstractmethod
    def model_drift_check_enum(self) -> Type["DeepchecksModelDriftCheck"]:
        """Return the enum class that contains the model drift checks.

        Returns:
            The enum class that contains the model drift checks.
        """

    @property
    def supported_checks(self) -> List[str]:
        """Return a list of all supported checks.

        Returns:
            A list of all supported checks.
        """
        return [
            check
            for check_enum in [
                self.data_validation_check_enum,
                self.data_drift_check_enum,
                self.model_validation_check_enum,
                self.model_drift_check_enum,
            ]
            for check in check_enum.values()
        ]

    def _create_and_run_check_suite(
        self,
        check_enum: Type[BaseDeepchecksValidationCheck],
        reference_dataset: Any,
        comparison_dataset: Optional[Any] = None,
        model: Optional[Any] = None,
        check_list: Optional[Sequence[str]] = None,
        dataset_kwargs: Dict[str, Any] = {},
        check_kwargs: Dict[str, Dict[str, Any]] = {},
        run_kwargs: Dict[str, Any] = {},
    ) -> SuiteResult:
        """Create and run a Deepchecks check suite.

        This method contains generic logic common to all Deepchecks data
        validator methods that validates the input arguments and uses them to
        generate and run a Deepchecks check suite.

        Args:
            check_enum: ZenML enum type grouping together Deepchecks checks with
                the same characteristics. This is used to generate a default
                list of checks, if a custom list isn't provided via the
                `check_list` argument.
            reference_dataset: Primary (reference) dataset argument used during
                validation.
            comparison_dataset: Optional secondary (comparison) dataset argument
                used during comparison checks.
            model: Optional model argument used during validation.
            check_list: Optional list of ZenML Deepchecks check identifiers
                specifying the list of Deepchecks checks to be performed.
            dataset_kwargs: Additional keyword arguments to be passed to the
                constructor of `self.dataset_class`.
            check_kwargs: Additional keyword arguments to be passed to the
                Deepchecks check object constructors. Arguments are grouped for
                each check and indexed using the full check class name or
                check enum value as dictionary keys.
            run_kwargs: Additional keyword arguments to be passed to the
                `run` method of the `self.suite_class` object.

        Returns:
            Deepchecks SuiteResult object with the Suite run results.

        Raises:
            TypeError: If the datasets, model and check list arguments are not
                compatible with the supported types of this data validator.
        """
        # Validate the dataset types
        for dataset in [reference_dataset, comparison_dataset]:
            if dataset is not None and not isinstance(
                dataset, self.supported_dataset_types
            ):
                raise TypeError(
                    f"Unsupported dataset data type found: {type(dataset)}. "
                    f"The {self.__class__.__name__} data validator can only "
                    f"handle the following dataset types: "
                    f"{list(self.supported_dataset_types)}."
                )

        # Validate the model type
        if model is not None and not isinstance(
            model, self.supported_model_types
        ):
            raise TypeError(
                f"Unsupported model data type found: {type(model)}. "
                f"The {self.__class__.__name__} data validator can only handle "
                f"the following model types: "
                f"{list(self.supported_model_types)}."
            )

        if not check_list:
            # default to executing all the checks listed in the supplied
            # checks enum type if a custom check list is not supplied
            check_list = check_enum.values()

        # Make sure all the checks in the supplied check list are valid
        else:
            for check_ in check_list:
                if check_ not in self.supported_checks:
                    raise TypeError(
                        f"Invalid check identifier found: {check_}. Only "
                        f" checks from `deepchecks.{self.deepchecks_module}` "
                        f"can be used with `{self.__class__.__name__}`."
                    )

        check_classes = map(
            lambda check: (
                check,
                check_enum.get_check_class(check),
            ),
            check_list,
        )

        # use the pipeline name and the step name to generate a unique suite
        # name
        try:
            # get pipeline name and step name
            step_env = cast(
                StepEnvironment, Environment()[STEP_ENVIRONMENT_NAME]
            )
            suite_name = f"{step_env.pipeline_name}_{step_env.step_name}"
        except KeyError:
            # if not running inside a pipeline step, use random values
            suite_name = f"suite_{random_str(5)}"

        train_dataset = self.dataset_class(reference_dataset, **dataset_kwargs)
        test_dataset = None
        if comparison_dataset is not None:
            test_dataset = self.dataset_class(
                comparison_dataset, **dataset_kwargs
            )
        suite = self.suite_class(name=suite_name)

        # Some Deepchecks checks require a minimum configuration such as
        # conditions to be configured (see https://docs.deepchecks.com/stable/user-guide/general/customizations/examples/plot_configure_check_conditions.html#sphx-glr-user-guide-general-customizations-examples-plot-configure-check-conditions-py)
        # for their execution to have meaning. For checks that don't have
        # custom configuration attributes explicitly specified in the
        # `check_kwargs` input parameter, we use the default check
        # instances extracted from the full suite shipped with Deepchecks.
        default_checks = {
            check.__class__: check for check in self.full_suite.checks.values()
        }
        for check_name, check_class in check_classes:
            extra_kwargs = check_kwargs.get(check_name, {})
            default_check = default_checks.get(check_class)
            check: BaseCheck
            if extra_kwargs or not default_check:
                check = check_class(**check_kwargs)
            else:
                check = default_check

            # extract the condition kwargs from the check kwargs
            for arg_name, condition_kwargs in extra_kwargs.items():
                if not arg_name.startswith("condition_") or not isinstance(
                    condition_kwargs, dict
                ):
                    continue
                condition_method = getattr(check, f"add_{arg_name}", None)
                if not condition_method or not callable(condition_method):
                    logger.warning(
                        f"Deepchecks check type {check.__class__} has no "
                        f"condition named {arg_name}. Ignoring the check "
                        f"argument."
                    )
                    continue
                condition_method(**condition_kwargs)

            suite.add(check)
        return suite.run(
            train_dataset=train_dataset,
            test_dataset=test_dataset,
            model=model,
            **run_kwargs,
        )

    def data_validation(
        self,
        dataset: Any,
        comparison_dataset: Optional[Any] = None,
        check_list: Optional[Sequence[str]] = None,
        dataset_kwargs: Dict[str, Any] = {},
        check_kwargs: Dict[str, Dict[str, Any]] = {},
        run_kwargs: Dict[str, Any] = {},
        **kwargs: Any,
    ) -> SuiteResult:
        """Run one or more Deepchecks data validation checks on a dataset.

        Call this method to analyze and identify potential integrity problems
        with a single dataset (e.g. missing values, conflicting labels, mixed
        data types etc.) and dataset comparison checks (e.g. data drift
        checks). Dataset comparison checks require that a second dataset be
        supplied via the `comparison_dataset` argument.

        The `check_list` argument may be used to specify a custom set of
        Deepchecks data integrity checks to perform, identified by
        `DeepchecksDataIntegrityCheck` and `DeepchecksDataDriftCheck` enum
        values. If omitted:

        * if the `comparison_dataset` is omitted, a suite with all available
        data integrity checks will be performed on the input data. See
        `DeepchecksDataIntegrityCheck` for a list of Deepchecks builtin
        checks that are compatible with this method.

        * if the `comparison_dataset` is supplied, a suite with all
        available data drift checks will be performed on the input
        data. See `DeepchecksDataDriftCheck` for a list of Deepchecks
        builtin checks that are compatible with this method.

        Args:
            dataset: Target dataset to be validated.
            comparison_dataset: Optional second dataset to be used for data
                comparison checks (e.g data drift checks).
            check_list: Optional list of ZenML Deepchecks check identifiers
                specifying the data validation checks to be performed.
                `DeepchecksDataIntegrityCheck` enum values should be used for
                single data validation checks and `DeepchecksDataDriftCheck`
                enum values for data comparison checks. If not supplied, the
                entire set of checks applicable to the input dataset(s)
                will be performed.
            dataset_kwargs: Additional keyword arguments to be passed to the
                Deepchecks `tabular.Dataset` or `vision.VisionData` constructor.
            check_kwargs: Additional keyword arguments to be passed to the
                Deepchecks check object constructors. Arguments are grouped for
                each check and indexed using the full check class name or
                check enum value as dictionary keys.
            run_kwargs: Additional keyword arguments to be passed to the
                Deepchecks Suite `run` method.
            kwargs: Additional keyword arguments (unused).

        Returns:
            A Deepchecks SuiteResult with the results of the validation.
        """
        check_enum: Type[BaseDeepchecksValidationCheck]
        if comparison_dataset is None:
            check_enum = self.data_validation_check_enum
        else:
            check_enum = self.data_drift_check_enum

        return self._create_and_run_check_suite(
            check_enum=check_enum,
            reference_dataset=dataset,
            comparison_dataset=comparison_dataset,
            check_list=check_list,
            dataset_kwargs=dataset_kwargs,
            check_kwargs=check_kwargs,
            run_kwargs=run_kwargs,
        )

    def model_validation(
        self,
        dataset: Any,
        model: Any,
        comparison_dataset: Optional[Any] = None,
        check_list: Optional[Sequence[str]] = None,
        dataset_kwargs: Dict[str, Any] = {},
        check_kwargs: Dict[str, Dict[str, Any]] = {},
        run_kwargs: Dict[str, Any] = {},
        **kwargs: Any,
    ) -> Any:
        """Run one or more Deepchecks model validation checks.

        Call this method to perform model validation checks (e.g. confusion
        matrix validation, performance reports, model error analyses, etc).
        A second dataset is required for model performance comparison tests
        (i.e. tests that identify changes in a model behavior by comparing how
        it performs on two different datasets).

        The `check_list` argument may be used to specify a custom set of
        Deepchecks model validation checks to perform, identified by
        `DeepchecksModelValidationCheck` and `DeepchecksModelDriftCheck` enum
        values. If omitted:

            * if the `comparison_dataset` is omitted, a suite with all available
            model validation checks will be performed on the input data. See
            `DeepchecksModelValidationCheck` for a list of Deepchecks builtin
            checks that are compatible with this method.

            * if the `comparison_dataset` is supplied, a suite with all
            available model comparison checks will be performed on the input
            data. See `DeepchecksModelValidationCheck` for a list of Deepchecks
            builtin checks that are compatible with this method.

        Args:
            dataset: Target dataset to be validated.
            model: Target model to be validated.
            comparison_dataset: Optional second dataset to be used for model
                comparison checks.
            check_list: Optional list of ZenML Deepchecks check identifiers
                specifying the model validation checks to be performed.
                `DeepchecksModelValidationCheck` enum values should be used for
                model validation checks and `DeepchecksModelDriftCheck` enum
                values for model comparison checks. If not supplied, the
                entire set of checks applicable to the input dataset(s)
                will be performed.
            dataset_kwargs: Additional keyword arguments to be passed to the
                Deepchecks tabular.Dataset or vision.VisionData constructor.
            check_kwargs: Additional keyword arguments to be passed to the
                Deepchecks check object constructors. Arguments are grouped for
                each check and indexed using the full check class name or
                check enum value as dictionary keys.
            run_kwargs: Additional keyword arguments to be passed to the
                Deepchecks Suite `run` method.
            kwargs: Additional keyword arguments (unused).

        Returns:
            A Deepchecks SuiteResult with the results of the validation.
        """
        check_enum: Type[BaseDeepchecksValidationCheck]
        if comparison_dataset is None:
            check_enum = self.model_validation_check_enum
        else:
            check_enum = self.model_drift_check_enum

        return self._create_and_run_check_suite(
            check_enum=check_enum,
            reference_dataset=dataset,
            comparison_dataset=comparison_dataset,
            model=model,
            check_list=check_list,
            dataset_kwargs=dataset_kwargs,
            check_kwargs=check_kwargs,
            run_kwargs=run_kwargs,
        )
