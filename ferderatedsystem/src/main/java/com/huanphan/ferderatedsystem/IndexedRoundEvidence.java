package com.huanphan.ferderatedsystem;

import com.fasterxml.jackson.core.JsonToken;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.io.RandomAccessFile;
import java.nio.file.Path;
import java.util.AbstractList;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.RandomAccess;

/** Read-only round evidence with byte offsets; no round trees or open handles are retained. */
final class IndexedRoundEvidence extends AbstractList<JsonNode> implements RandomAccess {
    private record Span(long start,int length) {}
    private final Path path;
    private final ObjectMapper json;
    private final List<Span> spans=new ArrayList<>();

    IndexedRoundEvidence(Path path,ObjectMapper json) throws IOException {
        this.path=path;this.json=json;
        try(var parser=json.getFactory().createParser(path.toFile())) {
            if(parser.nextToken()!=JsonToken.START_ARRAY) throw new IOException("Expected round array: "+path);
            while(parser.nextToken()!=JsonToken.END_ARRAY) {
                if(parser.currentToken()!=JsonToken.START_OBJECT) throw new IOException("Expected round object: "+path);
                long start=parser.currentTokenLocation().getByteOffset();
                parser.skipChildren();
                spans.add(new Span(start,Math.toIntExact(parser.currentLocation().getByteOffset()-start)));
            }
            if(parser.nextToken()!=null) throw new IOException("Trailing round evidence: "+path);
        }
    }

    @Override public int size() {return spans.size();}

    @Override public JsonNode get(int index) {
        Objects.checkIndex(index,size());var span=spans.get(index);
        try(var file=new RandomAccessFile(path.toFile(),"r")) {
            file.seek(span.start());byte[] bytes=new byte[span.length()];file.readFully(bytes);
            return json.readTree(bytes);
        } catch(IOException e) {throw new UncheckedIOException("Cannot read round evidence: "+path,e);}
    }
}
