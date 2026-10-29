package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import java.io.IOException;
import java.net.http.*;
import java.time.Duration;
import java.util.*;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class PythonMLClientTests {
    final ObjectMapper json=new ObjectMapper();
    @SuppressWarnings("unchecked")
    HttpResponse<String> response(int code,String body) {
        HttpResponse<String> r=mock(HttpResponse.class);when(r.statusCode()).thenReturn(code);when(r.body()).thenReturn(body);return r;
    }
    PythonMLClient client(HttpClient http,int attempts,List<Long> waits) {
        return new PythonMLClient(json,"http://localhost:8000",attempts,2000,30000,Duration.ofSeconds(1800),http,waits::add);
    }
    @Test void retriesTransportTimeoutGatewayAndKnownBusyWithBoundedBackoff() throws Exception {
        var http=mock(HttpClient.class);List<Long> waits=new ArrayList<>();
        when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenThrow(new HttpTimeoutException("paused"))
                .thenReturn(response(503,"temporary"),response(409,"{\"detail\":\"Worker busy; only one active ML operation allowed\"}"),response(200,"{\"ok\":true}"));
        assertTrue(client(http,4,waits).post("/simulation/round",Map.of("seed",45)).path("ok").asBoolean());
        assertEquals(List.of(2000L,4000L,8000L),waits);
        var requests=ArgumentCaptor.forClass(HttpRequest.class);verify(http,times(4)).send(requests.capture(),any(HttpResponse.BodyHandler.class));
        assertTrue(requests.getAllValues().stream().allMatch(r->r==requests.getValue()));
    }
    @Test void checkpointRetriesKeepOperationIdAndRecheckWorkerCapability() throws Exception {
        var http=mock(HttpClient.class);List<Long> waits=new ArrayList<>();
        var supported=response(200,"{\"idempotentCheckpointOperations\":true}");
        when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenReturn(supported).thenThrow(new IOException("response lost"))
                .thenReturn(supported,response(200,"{\"modelStateHash\":\"saved\"}"));
        var c=client(http,4,waits);
        assertEquals("saved",c.post("/train",Map.of("operationId","original-round-attempt","clientId",7)).path("modelStateHash").asText());
        var requests=ArgumentCaptor.forClass(HttpRequest.class);verify(http,times(4)).send(requests.capture(),any(HttpResponse.BodyHandler.class));
        var posts=requests.getAllValues().stream().filter(r->r.method().equals("POST")).toList();
        assertEquals(2,posts.size());assertSame(posts.get(0),posts.get(1));
        assertEquals("original-round-attempt",posts.get(1).headers().firstValue("X-MiniFLS-Attempt").orElseThrow());
        assertEquals(List.of(2000L),waits);
    }
    @Test void oldWorkerCannotReceiveAutomaticallyRetriedCheckpointRequests() throws Exception {
        var http=mock(HttpClient.class);var reply=response(200,"{}");when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenReturn(reply);
        assertTrue(assertThrows(IllegalStateException.class,()->client(http,4,new ArrayList<>()).post("/train",Map.of())).getMessage().contains("restart"));
        var request=ArgumentCaptor.forClass(HttpRequest.class);verify(http).send(request.capture(),any(HttpResponse.BodyHandler.class));assertEquals("GET",request.getValue().method());
    }
    @Test void applicationErrorsConflictsAndInvalidJsonAreNotRetried() throws Exception {
        for(int status:List.of(400,404,409,422,500)) {
            var http=mock(HttpClient.class);List<Long> waits=new ArrayList<>();
            var reply=response(status,"{\"detail\":\"request mismatch\"}");
            when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenReturn(reply);
            var failure=assertThrows(IllegalStateException.class,()->client(http,4,waits).get("/health"));
            assertTrue(failure.getMessage().contains("HTTP "+status));verify(http).send(any(),any(HttpResponse.BodyHandler.class));assertTrue(waits.isEmpty());
        }
        var http=mock(HttpClient.class);var reply=response(200,"broken JSON");when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenReturn(reply);
        assertTrue(assertThrows(IllegalStateException.class,()->client(http,4,new ArrayList<>()).get("/health")).getMessage().contains("Invalid JSON"));
        verify(http).send(any(),any(HttpResponse.BodyHandler.class));
    }
    @Test void exhaustionRetainsRouteAttemptCountAndRootCause() throws Exception {
        var http=mock(HttpClient.class);var cause=new IOException("connection reset");List<Long> waits=new ArrayList<>();
        when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenThrow(cause);
        var error=assertThrows(IllegalStateException.class,()->client(http,3,waits).get("/runtime"));
        assertSame(cause,error.getCause());assertTrue(error.getMessage().contains("route=/runtime"));assertTrue(error.getMessage().contains("attempts=3/3"));assertTrue(error.getMessage().contains("connection reset"));
        verify(http,times(3)).send(any(),any(HttpResponse.BodyHandler.class));assertEquals(List.of(2000L,4000L),waits);
    }
    @Test void cancellationStopsRetriesAndPreservesThreadInterrupt() throws Exception {
        var http=mock(HttpClient.class);when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenThrow(new IOException("unavailable"));
        var c=new PythonMLClient(json,"http://localhost",4,2000,30000,Duration.ofSeconds(1800),http,millis->{throw new InterruptedException("stop");});
        try {
            assertThrows(IllegalStateException.class,()->c.get("/health"));assertTrue(Thread.currentThread().isInterrupted());verify(http).send(any(),any(HttpResponse.BodyHandler.class));
        } finally {Thread.interrupted();}
    }
    @Test void singleAttemptDisablesRetriesAndCheckpointCapabilityProbe() throws Exception {
        var http=mock(HttpClient.class);var reply=response(200,"{\"ok\":true}");when(http.send(any(),any(HttpResponse.BodyHandler.class))).thenReturn(reply);
        assertTrue(client(http,1,new ArrayList<>()).post("/train",Map.of()).path("ok").asBoolean());
        var request=ArgumentCaptor.forClass(HttpRequest.class);verify(http).send(request.capture(),any(HttpResponse.BodyHandler.class));assertEquals("POST",request.getValue().method());
    }
    @Test void retryConfigurationIsValidatedAndPolicyIsInspectable() {
        assertThrows(IllegalArgumentException.class,()->client(mock(HttpClient.class),0,new ArrayList<>()));
        assertEquals(4,client(mock(HttpClient.class),4,new ArrayList<>()).retryPolicy().get("maxAttempts"));
    }
}
