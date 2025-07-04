import asyncio
import collections
from typing import TypeVar, Literal

from loguru import logger as logging
from pydantic import BaseModel

from smarttel.seestar.commands.imaging import BeginStreaming, StopStreaming, GetStackedImage
from smarttel.seestar.commands.simple import TestConnection
from smarttel.seestar.connection import SeestarConnection
from smarttel.seestar.events import EventTypes, AnnotateResult, BaseEvent, StackEvent
from smarttel.seestar.protocol_handlers import BinaryProtocol, ScopeImage
from smarttel.util.eventbus import EventBus

U = TypeVar("U")


class SeestarImagingStatus(BaseModel):
    """Seestar imaging status."""
    temp: float | None = None
    charger_status: Literal['Discharging', 'Charging', 'Full'] | None = None
    charge_online: bool | None = None
    battery_capacity: int | None = None
    stacked_frame: int = 0
    dropped_frame: int = 0
    target_name: str = ""
    annotate: AnnotateResult | None = None
    is_streaming: bool = False
    is_fetching_images: bool = False

    def reset(self):
        self.temp = None
        self.charger_status = None
        self.charge_online = None
        self.battery_capacity = None
        self.stacked_frame = 0
        self.dropped_frame = 0
        self.target_name = ""
        self.annotate = None
        self.is_streaming = False


class ParsedEvent(BaseModel):
    """Parsed event."""
    event: EventTypes


class SeestarImagingClient(BaseModel, arbitrary_types_allowed=True):
    """Seestar imaging client."""
    host: str
    port: int
    connection: SeestarConnection | None = None
    id: int = 100
    is_connected: bool = False
    status: SeestarImagingStatus = SeestarImagingStatus()
    background_task: asyncio.Task | None = None
    reader_task: asyncio.Task | None = None
    recent_events: collections.deque = collections.deque(maxlen=5)
    event_bus: EventBus | None = None
    binary_protocol: BinaryProtocol = BinaryProtocol()
    image: ScopeImage | None = None

    def __init__(self, host: str, port: int, event_bus: EventBus | None = None):
        super().__init__(host=host, port=port, event_bus=event_bus)

        self.event_bus.add_listener('Stack', self._handle_stack_event)
        self.connection = SeestarConnection(host=host, port=port)

    async def _reader(self):
        """Background task that continuously reads messages and handles them."""
        logging.info(f"Starting reader task for {self}")
        while self.is_connected:
            try:
                # Check if connection is still valid
                if not self.connection.is_connected():
                    logging.warning(f"Connection lost for {self}, attempting to reconnect...")
                    await asyncio.sleep(1.0)  # Wait before next iteration
                    continue
                    
                header = await self.connection.read_exactly(80)
                if header is None:
                    # Connection issue handled by connection layer, check status and continue
                    if not self.connection.is_connected():
                        logging.debug(f"Connection not available for {self}, will retry")
                        await asyncio.sleep(0.5)
                    continue
                    
                size, id, width, height = self.binary_protocol.parse_header(header)
                logging.trace(f"imaging receive header: {size=} {width=} {height=} {id=}")
                
                data = None
                if size is not None:
                    data = await self.connection.read_exactly(size)
                    if data is None:
                        # Connection issue during data read, check status and continue
                        if not self.connection.is_connected():
                            logging.debug(f"Connection lost during data read for {self}")
                            await asyncio.sleep(0.5)
                        continue
                        
                if data is not None:
                    self.image = await self.binary_protocol.handle_incoming_message(width, height, data, id)

            except Exception as e:
                logging.error(f"Unexpected error in imaging reader task for {self}: {e}")
                if self.is_connected:
                    await asyncio.sleep(1.0)  # Brief pause before retrying
                    continue
                else:
                    break
        logging.info(f"Reader task stopped for {self}")

    async def _heartbeat(self):
        await asyncio.sleep(5)
        while True:
            if self.is_connected:
                logging.trace(f"Pinging {self}")
                await self.send(TestConnection())
            await asyncio.sleep(5)

    async def connect(self):
        await self.connection.open()
        self.is_connected = True
        self.status.reset()

        self.background_task = asyncio.create_task(self._heartbeat())
        self.reader_task = asyncio.create_task(self._reader())

        logging.info(f"Connected to {self}")

    async def disconnect(self):
        """Disconnect from Seestar."""
        if self.status.is_streaming:
            await self.stop_streaming()
        await self.connection.close()
        self.is_connected = False
        logging.info(f"Disconnected from {self}")

    async def send(self, data: str | BaseModel):
        if isinstance(data, BaseModel):
            if data.id is None:
                data.id = self.id
                self.id += 1
            data = data.model_dump_json()
        await self.connection.write(data)

    async def get_next_image(self):
        last_image: ScopeImage | None = None

        self.status.is_fetching_images = True
        while self.is_connected:
            if self.image is not None and self.image != last_image:
                last_image = self.image
                yield self.image
            await asyncio.sleep(0.01)
        self.status.is_fetching_images = False

    async def _handle_stack_event(self, event: BaseEvent):
        if event.state == 'frame_complete' and self.status.is_fetching_images:
            # Only grab the frame if we're streaming in client!
            logging.trace("Grabbing frame")
            await self.send(GetStackedImage(id=23))

    async def start_streaming(self):
        """Start streaming from the Seestar."""
        if self.status.is_streaming:
            logging.warning(f"Already streaming from {self}")
            return

        _ = await self.send(BeginStreaming(id=21))
        self.status.is_streaming = True
        # if response and response.result is not None:
        #     self.status.is_streaming = True
        #     logging.info(f"Started streaming from {self}")
        # else:
        #     logging.error(f"Failed to start streaming from {self}: {response}")

    async def stop_streaming(self):
        """Stop streaming from the Seestar."""
        if not self.status.is_streaming:
            logging.warning(f"Not streaming from {self}")
            return

        response = await self.send(StopStreaming())
        self.status.is_streaming = False

    def __str__(self):
        return f"{self.host}:{self.port}"
