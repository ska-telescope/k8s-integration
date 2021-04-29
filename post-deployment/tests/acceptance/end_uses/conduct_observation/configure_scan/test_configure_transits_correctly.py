import pytest
from time import sleep
from contextlib import contextmanager
from sys import intern
from types import SimpleNamespace
from typing import Any, Iterator, List, NamedTuple, Tuple, Union
from pytest_bdd import scenario, given, when, then
from skallop.event_handling import builders
from skallop.mvp_fixtures import telescope as tel_fxt
from skallop.mvp_fixtures import types as fxt_types
from skallop.mvp_control.entry_points import oet
from skallop.mvp_control.entry_points import base
from skallop.mvp_control.entry_points import types
from skallop.mvp_control.describing import mvp_names
from skallop.event_handling import logging as log
from skallop.mvp_control.event_waiting import wait
from skallop.mvp_fixtures import subarray_composition as sub_comp_fxt
from skallop.mvp_control.subarray import compose
from skallop.mvp_control.subarray import configure
from skallop.subscribing import producers
import logging
import mock


logger = logging.getLogger("__name__")

class ScanConfigArgs(NamedTuple):
    subarray_id: int
    receptors: List[int]
    configuration: types.ConfigurationByFile
    devices_to_log: List[log.DeviceLogSpec]
    time_out: int
    live_logging: bool
    filter_logs: bool
    log_filter_pattern: str

class ExecutionContext(SimpleNamespace):
    pass


# background fixtures
@given("A running telescope for executing observations on a subarray")
def a_running_telescope(running_telescope):
    pass


@pytest.mark.skamid
@scenario(
    "configure_transitions.feature",
    "Configure a scan using a predefined config",
    example_converters=dict(nr_of_dishes=int, subarray_id=int,
                            SB_config=str, scan_config=str),
)
def test_configure_transits_correctly():
    pass


@given("subarray <subarray_id> that has been allocated <nr_of_dishes> according to <SB_config>")
def allocated_subarray(composed_subarray):
    """The composed_subarray fixture assigns dishes and other resources and returns
    only after the subarray transitioned to IDLE. It uses subarray_id, nr_of_dishes and SB_config as the
    input paramaters.

    Args:
        composed_subarray ([type]): the fixture 
    """
    # needs to pass subarray_id nr_of_dishes SB_config as paramaters to composed_subarray fixture
    pass


@when("I configure the subarray to perform a <scan_config> scan")
def configure_subarray(
    prepare_for_configure, # name should include maybe
    entry_point: oet.EntryPoint,
    scan_config_args: ScanConfigArgs,
    context: ExecutionContext, # name is maybe to general
):
    args = scan_config_args
    entry_point.configure_subarray(args.subarray_id, args.receptors, args.configuration)


@then("the tmc subarray transits to READY state after sdp subarray and csp subarray has done so")
def check_transits_correctly(scan_config_args: ScanConfigArgs, context: ExecutionContext):
    args = scan_config_args
    wait.wait(context.board, args.time_out, args.live_logging)
    context.state = "configured"
    board: builders.MessageBoard = context.board
    checker: builders.Occurrences = context.checker
    logs = board.play_log_book(args.filter_logs, args.log_filter_pattern)
    logger.info(f"Log messages during waiting:\n{logs}")
    checking_logs = checker.print_outcome_for(checker.subject_device)
    logger.info(f"Results of checking transitions:\n{checking_logs}")
    #checker.assert_that(checker.subject_device).is_behind_all_on_transit("CONFIGURING")
    checker.assert_that(checker.subject_device).is_behind_all_on_transit("READY")


## fixtures ##

@pytest.fixture(name='context')
def fxt_context()->ExecutionContext:
    return ExecutionContext()

@pytest.fixture(name='entry_point')
def fxt_entry_point(context) -> base.EntryPoint:
    entry_point = oet.EntryPoint()
    return entry_point

@pytest.fixture(name='subarray_internals')
def fxt_subarray_internals(subarray_id: int) -> List[str]:
    return mvp_names.SubArrays(subarray_id).subtract("tm").subtract("cbf domain").list


# fixture arguments
# running telescope
# overrides base fixture


@pytest.fixture(name='running_telescope_args')
def fxt_running_telescope_args(entry_point):
    return tel_fxt.RunningTelescopeArgs(
        entry_point=entry_point,
        log_enabled=False,
        log_spec=[],
        play_logbook=fxt_types.PlaySpec(False),
    )

# overrides composed subarray fixture args
@pytest.fixture(name='composed_subarray_args')
def fxt_composed_subarray_args(tmp_path, SB_config, nr_of_dishes, subarray_id: int, entry_point):
    if SB_config == "standard":
        composition = sub_comp_fxt.conf_types.CompositionByFile(
            tmp_path, sub_comp_fxt.conf_types.FileCompositionType.standard
        )
    else:
        raise NotImplementedError("configuration type {SB_config} not implemented")
    return sub_comp_fxt.Args(
        subarray_id=subarray_id,
        entry_point=entry_point,
        receptors=list(range(1, nr_of_dishes + 1)),
        composition=composition,
    )



@pytest.fixture(name='scan_config_args')
def fxt_scan_config_args(
    tmp_path,
    scan_config: str,
    nr_of_dishes: int,
    subarray_id: int,
    composed_subarray_args: sub_comp_fxt.Args,
) -> ScanConfigArgs:

    receptors = list(range(1, nr_of_dishes + 1))
    devices_to_log = [
        log.DeviceLogSpec(device)
        for device in mvp_names.SubArrays(subarray_id).subtract("cbf domain")
    ]
    # note the composition.metadata in order to tie the ids together
    if scan_config == "standard":
        configuration = types.ConfigurationByFile(
            tmp_path,
            types.FileConfigurationType.standard,
            composed_subarray_args.composition.metadata,
        )
    else:
        raise NotImplementedError(f"{scan_config}")
    return ScanConfigArgs(
        subarray_id,
        receptors,
        configuration,
        devices_to_log,
        time_out=5,
        live_logging=False,
        filter_logs=False,
        log_filter_pattern=r"Transaction\[txn",
    )


@pytest.fixture(name='scan_transitions')
def fxt_scan_transitions() -> List[Union[str, Tuple[str, str]]]:
    return ["IDLE", ("CONFIGURING", "ahead"), "READY"]




@pytest.fixture(name='checking_transits_during_configuration')
def fxt_checking_transits_during_configuration(subarray_id: int, scan_transitions: List[Union[str, Tuple[str, str]]], subarray_internals: List[str]) -> Tuple[builders.Occurrences, builders.MessageBoardBuilder]:
    """sets up an object that checks for transitions to occur on  given set of devices in a given order

    Args:
        subarray_id (int): the subarray instance in use
        scan_transitions (List[Union[str, Tuple[str, str]]]): a list of events that the subjects are expected to transition to
        subarray_internals (List[str]): a list containing the internal components (e.g. sdp and csp) for which their transitions will be monitored
        relative to that of the subarray node

    Returns:
        Tuple[builders.Occurrences, builders.MessageBoardBuilder]: the occurrences object that will be used to hold record of occurrences as well as the messageboard builder that will set
        up subscriptions to populate these occurrences.
    """
    
    builder = builders.MessageBoardBuilder()
    subarray_node = str(mvp_names.Mid.tm.subarray(subarray_id))
    checker = (
        builder.check_that(subarray_node)
        .transits_according_to(scan_transitions)
        .on_attr("obsState")
        .when_transist_occur_on(subarray_internals)
    )
    return checker, builder


@pytest.fixture(name='clear_args')
def fxt_clear_args(
    scan_config_args: ScanConfigArgs, entry_point: oet.EntryPoint
) -> configure.ConFigureSubarrayArgs:
    return configure.ConFigureSubarrayArgs(
        scan_config_args.subarray_id,
        scan_config_args.receptors,
        entry_point=entry_point,
        configuration=scan_config_args.configuration,
    )


@pytest.fixture(name='prepare_for_configure')
def fxt_prepare_for_configure(
    clear_args: configure.ConFigureSubarrayArgs,
    scan_config_args: ScanConfigArgs,
    checking_transits_during_configuration: Tuple[
        builders.Occurrences, builders.MessageBoardBuilder
    ],
    execution_context: ExecutionContext,
):
    """ prepare for the configuration command by performing pre checks and post tear down steps as well
    as setting up monitoring asynchronously whilst performing the command.

    Args:
        clear_args (configure.ConFigureSubarrayArgs): the arguments to use when clearing the configuration of the subarray (fixture)
        scan_config_args (ScanConfigArgs): the arguments that will be used in configuration step to obtain data for checking scan can be done.
        checking_transits_during_configuration (Tuple[ builders.Occurrences, builders.MessageBoardBuilder ]): a predefined monitoring builder set up to
        record a set of occurrences expected during the execution of the configure command as well as the occurrences object that will contain the data.
        execution_context (ExecutionContext): An container holding references to the occurrences and messageboard being populated with data during execution of configure command.
    """
    execution_context.checker, builder = checking_transits_during_configuration
    configure.assert_I_can_configure_a_subarray(
        scan_config_args.subarray_id, scan_config_args.receptors
    )
    with wait.waiting_context(builder) as board:
        execution_context.board = board
        # holds a reference to the board for future use
        with configure.tear_down_when_finished(clear_args):
            yield

