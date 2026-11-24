import java.awt.event.KeyEvent;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import javax.swing.SwingUtilities;

/**
 * Headless smoke test for UdpGestureListener. No window is shown.
 *
 * Run from the repo root (see run.sh for the full build):
 *   javac -d build/test game/src/*.java game/test/*.java
 *   java -Djava.awt.headless=true -cp build/test:game/src HeadlessFlapTest
 */
public class HeadlessFlapTest {
    static final int PORT = 15005; // a test port, so it never clashes with a running game
    static int failures = 0;

    public static void main(String[] args) throws Exception {
        final FlappyBird[] holder = new FlappyBird[1];
        SwingUtilities.invokeAndWait(() -> holder[0] = new FlappyBird());
        FlappyBird game = holder[0];

        // Freeze the physics so velocityY stays at the value the flap sets.
        SwingUtilities.invokeAndWait(() -> {
            game.gameLoop.stop();
            game.placePipeTimer.stop();
        });

        UdpGestureListener listener = new UdpGestureListener(game, PORT);
        listener.start();

        // 1. FLAP makes the bird jump exactly like SPACE does.
        send("FLAP");
        Thread.sleep(200);
        check("FLAP jumps (velocityY == -9)", onEdt(() -> game.velocityY) == -9);

        // 2. SPACE still works as before.
        SwingUtilities.invokeAndWait(() -> {
            game.velocityY = 0;
            game.keyPressed(new KeyEvent(game, KeyEvent.KEY_PRESSED, 0, 0, KeyEvent.VK_SPACE, ' '));
        });
        check("SPACE jumps (velocityY == -9)", onEdt(() -> game.velocityY) == -9);

        // 3. A second listener on the same port must not throw; it just stays disabled.
        UdpGestureListener busy = new UdpGestureListener(game, PORT);
        busy.start();
        check("busy port does not crash", true);

        // 4. Within the lockout after game over, FLAP must NOT restart the game.
        SwingUtilities.invokeAndWait(() -> {
            game.gameOver = true;
            game.gameOverAt = System.currentTimeMillis();
        });
        send("FLAP");
        Thread.sleep(200);
        check("FLAP ignored right after game over", onEdt(() -> game.gameOver));

        // 5. After the lockout, FLAP restarts the game.
        SwingUtilities.invokeAndWait(() -> game.gameOverAt = System.currentTimeMillis() - 2000);
        send("FLAP");
        Thread.sleep(200);
        SwingUtilities.invokeAndWait(() -> game.gameLoop.stop());
        check("FLAP restarts after lockout", !onEdt(() -> game.gameOver));

        System.out.println(failures == 0 ? "ALL PASSED" : failures + " CHECK(S) FAILED");
        System.exit(failures == 0 ? 0 : 1);
    }

    static void send(String message) throws Exception {
        try (DatagramSocket socket = new DatagramSocket()) {
            byte[] data = message.getBytes("US-ASCII");
            socket.send(new DatagramPacket(data, data.length,
                    InetAddress.getByAddress(new byte[] {127, 0, 0, 1}), PORT));
        }
    }

    interface Getter<T> { T get(); }

    static <T> T onEdt(final Getter<T> getter) throws Exception {
        final Object[] result = new Object[1];
        SwingUtilities.invokeAndWait(() -> result[0] = getter.get());
        @SuppressWarnings("unchecked")
        T value = (T) result[0];
        return value;
    }

    static void check(String name, boolean ok) {
        System.out.println((ok ? "PASS  " : "FAIL  ") + name);
        if (!ok) {
            failures++;
        }
    }
}
