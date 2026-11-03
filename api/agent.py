"""Read-only AG-UI observation endpoint for CopilotKit and other AG-UI clients."""
import asyncio
import json
import time
from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ConfigDict
from adapters.transport.ag_ui import AgentEventBridge, encode


class ObserveInput(BaseModel):
    model_config = ConfigDict(extra='ignore')
    threadId: str = Field(min_length=1, max_length=128)
    runId: str = Field(min_length=1, max_length=128)
    forwardedProps: dict = Field(default_factory=dict)


def register_agent_routes(app, repository):
    @app.post('/api/agent')
    def observe(body: ObserveInput, request: Request):
        rid = body.forwardedProps.get('search_id')
        if not isinstance(rid, str) or len(rid) != 32 or repository.run(rid) is None:
            raise HTTPException(404, 'Search not found. Start or select a search first.')

        async def packets():
            bridge = AgentEventBridge()
            yield encode('RUN_STARTED', threadId=body.threadId, runId=body.runId)
            initial=repository.run(rid)
            yield encode('STATE_SNAPSHOT', snapshot={'search': initial})
            last_status=initial['status']
            cursor, heartbeat = 0, time.monotonic()
            while True:
                if await request.is_disconnected():
                    return
                # Snapshot before the final event read, as in the native SSE path.
                current = repository.run(rid)
                if current['status']!=last_status:
                    yield encode('STATE_SNAPSHOT', snapshot={'search': current})
                    last_status=current['status']
                for item in repository.events(rid, cursor):
                    cursor = item['seq']
                    for encoded in bridge.activity(item):
                        yield encoded
                if current['status'] not in ('running','stopping'):
                    for encoded in bridge.finish():
                        yield encoded
                    yield encode('STATE_SNAPSHOT', snapshot={'search': current})
                    if current['status'] in ('complete','stopped'):
                        yield encode('RUN_FINISHED', threadId=body.threadId, runId=body.runId)
                    else:
                        yield encode('RUN_ERROR', message=current['error'] or 'Search stopped.', code='SEARCH_' + current['status'].upper())
                    return
                if time.monotonic() - heartbeat > 10:
                    yield encode('CUSTOM', name='proof.heartbeat', value={'search_id': rid})
                    heartbeat = time.monotonic()
                await asyncio.sleep(.25)
        return StreamingResponse(packets(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})

    @app.get('/api/searches/{rid}/trace')
    def trace(rid: str):
        run = repository.run(rid)
        if run is None:
            raise HTTPException(404, 'Search not found.')
        payload = {'version': 1, 'run': run, 'events': repository.events(rid)}
        return Response(json.dumps(payload, indent=2), media_type='application/json',
                        headers={'Content-Disposition': 'attachment; filename="proof-trace.json"'})
