package com.huanphan.ferderatedsystem;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ControlledAblationIdeLauncherTests {
    @Test void fullUnlimitedAndPreflightOptionsAreSupported() {
        var options=ControlledAblationIdeLauncher.arguments(new String[]{"--stage=full","--run-budget=0","--round-budget=0"});
        assertEquals("full",options.get("stage"));assertEquals("0",options.get("run-budget"));
        assertEquals("preflight",ControlledAblationIdeLauncher.arguments(new String[]{"--mode=preflight"}).get("mode"));
    }
    @Test void invalidOrAmbiguousOptionsFailClosed() {
        assertThrows(IllegalArgumentException.class,()->ControlledAblationIdeLauncher.arguments(new String[]{"--stage=full","--stage=pilot"}));
        assertThrows(IllegalArgumentException.class,()->ControlledAblationIdeLauncher.arguments(new String[]{"--run-budget=-1"}));
        assertThrows(IllegalArgumentException.class,()->ControlledAblationIdeLauncher.arguments(new String[]{"--stage=unknown"}));
        assertThrows(IllegalArgumentException.class,()->ControlledAblationIdeLauncher.arguments(new String[]{"--skip-integrity=true"}));
    }
}
