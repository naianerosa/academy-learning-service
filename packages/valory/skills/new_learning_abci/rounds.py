# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains the rounds of LearningAbciApp."""

from enum import Enum
from typing import Dict, FrozenSet, Optional, Set, Tuple

from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    CollectionRound,
    DegenerateRound,
    DeserializedCollection,
    EventToTimeout,
    get_name,
)
from packages.valory.skills.new_learning_abci.payloads import (    
    PingPayload
)


class Event(Enum):
    """NewLearningAbciApp Events"""

    DONE = "done"
    ERROR = "error"
    TRANSACT = "transact"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application, so all the agents share the same data.
    """

    def _get_deserialized(self, key: str) -> DeserializedCollection:
        """Strictly get a collection and return it deserialized."""
        serialized = self.db.get_strict(key)
        return CollectionRound.deserialize_collection(serialized)

    @property
    def ping_message(self) -> Optional[str]:
        """Get the coingeko ping message."""
        return self.db.get("ping_message", None)

    @property
    def participant_to_ping_round(self) -> DeserializedCollection:
        """Agent to payload mapping for the PingRound."""
        return self._get_deserialized("participant_to_ping_round")

class PingRound(CollectSameUntilThresholdRound):
    """PingRound"""   

    payload_class = PingPayload
    synchronized_data_class = SynchronizedData
    done_event = Event.DONE
    no_majority_event = Event.NO_MAJORITY 
    collection_key = get_name(SynchronizedData.participant_to_ping_round)
    selection_key = get_name(SynchronizedData.ping_message)

class FinishedPingRound(DegenerateRound):
    """FinishedPingRound"""


class NewLearningAbciApp(AbciApp[Event]):
    """NewLearningAbciApp"""

    initial_round_cls: AppState = PingRound
    initial_states: Set[AppState] = {
        PingRound,
    }
    transition_function: AbciAppTransitionFunction = {
        PingRound: {
            Event.NO_MAJORITY: PingRound,
            Event.ROUND_TIMEOUT: PingRound,
            Event.DONE: FinishedPingRound,
        },        
        FinishedPingRound: {},
    }
    final_states: Set[AppState] = {
        FinishedPingRound
    }
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        PingRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedPingRound: set(),
    }
