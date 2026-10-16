package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;

@Component
public class PythonMLClient {
    private final HttpClient client=HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1).connectTimeout(Duration.ofSeconds(10)).build();
    private final ObjectMapper json;
    private final String baseUrl;
    public PythonMLClient(ObjectMapper json,@Value("${minifls.worker-url}") String baseUrl) {this.json=json;this.baseUrl=baseUrl;}
    public JsonNode get(String route) {return request(route,null);}
    public JsonNode post(String route,Object payload) {return request(route,payload);}
    private JsonNode request(String route,Object payload) {
        try {
            var builder=HttpRequest.newBuilder(URI.create(baseUrl+route)).timeout(Duration.ofMinutes(30));
            if(payload!=null) builder.header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(payload)));
            else builder.GET();
            var response=client.send(builder.build(),HttpResponse.BodyHandlers.ofString());
            if(response.statusCode()/100!=2) throw new IllegalStateException("Worker HTTP "+response.statusCode()+": "+response.body());
            return json.readTree(response.body());
        } catch(InterruptedException e) {Thread.currentThread().interrupt();throw new IllegalStateException("Worker call interrupted",e);}
        catch(java.io.IOException e) {throw new IllegalStateException("Worker unavailable",e);}
    }
}
