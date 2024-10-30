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

"""This package contains round behaviours of NewLearningAbciApp."""

import json
from abc import ABC
from pathlib import Path
from tempfile import mkdtemp
from typing import Dict, Generator, Optional, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.abstract_round_abci.io_.store import SupportedFiletype
from packages.valory.skills.new_learning_abci.models import (
    CoingeckoPingSpecs,
    Params,
    SharedState,
)
from packages.valory.skills.new_learning_abci.payloads import (    
    PingPayload
)
from packages.valory.skills.new_learning_abci.rounds import (    
    Event,
    PingRound,
    SynchronizedData,
    NewLearningAbciApp
)

# Define some constants
ZERO_VALUE = 0
HTTP_OK = 200
GNOSIS_CHAIN_ID = "gnosis"
EMPTY_CALL_DATA = b"0x"
SAFE_GAS = 0
VALUE_KEY = "value"
TO_ADDRESS_KEY = "to_address"
METADATA_FILENAME = "metadata.json"


class NewLearningBaseBehaviour(BaseBehaviour, ABC):  # pylint: disable=too-many-ancestors
    """Base behaviour for the new_learning_abci behaviours."""

    @property
    def params(self) -> Params:
        """Return the params. Configs go here"""
        return cast(Params, super().params)

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data. This data is common to all agents"""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def local_state(self) -> SharedState:
        """Return the local state of this particular agent."""
        return cast(SharedState, self.context.state)
    
    @property
    def coingecko_ping_specs(self) -> CoingeckoPingSpecs:
        """Get the Coingecko api specs for Ping call."""
        return self.context.coingecko_ping_specs

    @property
    def metadata_filepath(self) -> str:
        """Get the temporary filepath to the metadata."""
        return str(Path(mkdtemp()) / METADATA_FILENAME)

    def get_sync_timestamp(self) -> float:
        """Get the synchronized time from Tendermint's last block."""
        now = cast(
            SharedState, self.context.state
        ).round_sequence.last_round_transition_timestamp.timestamp()

        return now

class PingBehaviour(NewLearningBaseBehaviour):
    """This behavior performs an ping call to Coingecko"""
    
    matching_round: Type[AbstractRound] = PingRound

    def async_act(self) -> Generator:
        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            sender = self.context.agent_address

            ping_message = yield from self.ping_coingecko()
            message_hash = yield from self.send_message_to_ipfs(ping_message)
            message_from_ipfs = yield from self.get_message_from_ipfs(message_hash)

            payload = PingPayload(sender, message_from_ipfs)
        
        # Send the payload to all agents and mark the behaviour as done
        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()
    
    def ping_coingecko(self) -> Generator[None, None, Optional[str]]:
        """Ping Coingecko using ApiSpecs"""

        # Get the specs
        specs = self.coingecko_ping_specs.get_spec()

        # Make the call
        raw_response = yield from self.get_http_response(**specs)
        
        # Process the response
        response = self.coingecko_ping_specs.process_response(raw_response)
        self.context.logger.info(f"Got ping reply from Coingecko using specs: {response}")
        
        return response

    def send_message_to_ipfs(self, message) -> Generator[None, None, Optional[str]]:
        """Store the ping message in IPFS"""
        data = {"ping_message": message}
        message_ipfs_hash = yield from self.send_to_ipfs(
            filename=self.metadata_filepath, obj=data, filetype=SupportedFiletype.JSON
        )
        self.context.logger.info(
            f"Ping Message stored in IPFS: https://gateway.autonolas.tech/ipfs/{message_ipfs_hash}"
        )
        return message_ipfs_hash
    
    def get_message_from_ipfs(self, message_ipfs_hash) -> Generator[None, None, Optional[str]]:
        """Load the message from IPFS"""        
        message = yield from self.get_from_ipfs(
            ipfs_hash=message_ipfs_hash, filetype=SupportedFiletype.JSON
        )
        self.context.logger.error(f"Got message from IPFS: {message}")
        return message["ping_message"]

class NewLearningRoundBehaviour(AbstractRoundBehaviour):
    """LearningRoundBehaviour"""

    initial_behaviour_cls = PingBehaviour
    abci_app_cls = NewLearningAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [  # type: ignore       
        PingBehaviour,
    ]