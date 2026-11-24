import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import javax.swing.SwingUtilities;

/**
 * Receives UDP messages from the webcam tracker (tracker/tracker.py).
 *
 *   FLAP  -> does exactly what SPACE does (and restarts after game over)
 *
 * The socket is bound to 127.0.0.1 only and read on a daemon thread. Every
 * call into the game is moved to the Swing thread. If the port is already in
 * use, the game still runs with the keyboard only.
 */
public class UdpGestureListener {
    public static final int DEFAULT_PORT = 5005;

    private final FlappyBird game;
    private final int port;
    private final DatagramSocket socket; // null if the port could not be bound

    public UdpGestureListener(FlappyBird game, int port) {
        this.game = game;
        this.port = port;
        DatagramSocket s = null;
        try {
            InetAddress loopback = InetAddress.getByAddress(new byte[] {127, 0, 0, 1});
            s = new DatagramSocket(new InetSocketAddress(loopback, port));
        } catch (IOException e) {
            System.out.println("WARNING: gesture control disabled, UDP 127.0.0.1:" + port
                    + " is unavailable (" + e.getMessage() + "). The keyboard (SPACE) still works.");
        }
        this.socket = s;
    }

    /** Starts the background receive thread. Does nothing if the port was not bound. */
    public void start() {
        if (socket == null) {
            return;
        }
        Thread thread = new Thread(this::receiveLoop, "udp-gesture-listener");
        thread.setDaemon(true);
        thread.start();
        System.out.println("Gesture control: listening on UDP 127.0.0.1:" + port);
    }

    private void receiveLoop() {
        byte[] buffer = new byte[256];
        while (true) {
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            try {
                socket.receive(packet);
            } catch (IOException e) {
                System.out.println("WARNING: gesture listener stopped: " + e.getMessage());
                return;
            }
            String message = new String(packet.getData(), packet.getOffset(), packet.getLength(),
                    StandardCharsets.US_ASCII).trim();
            handle(message);
        }
    }

    private void handle(String message) {
        if (message.equals("FLAP")) {
            SwingUtilities.invokeLater(game::handleFlap);
        }
    }
}
