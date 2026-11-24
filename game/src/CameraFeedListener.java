import java.awt.Color;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.Graphics;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.util.function.Consumer;
import javax.imageio.ImageIO;
import javax.swing.JPanel;

/**
 * Receives the webcam image from the tracker (tracker/tracker.py), one JPEG per UDP datagram,
 * and hands each decoded frame to a consumer. The tracker draws the hand on the image.
 *
 * Bound to 127.0.0.1 only and read on a daemon thread. If the port is already in use,
 * the game runs without the camera panel.
 */
public class CameraFeedListener {
    public static final int DEFAULT_PORT = 5006;

    private final Consumer<BufferedImage> onFrame;
    private final DatagramSocket socket; // null if the port could not be bound

    public CameraFeedListener(int port, Consumer<BufferedImage> onFrame) {
        this.onFrame = onFrame;
        DatagramSocket s = null;
        try {
            InetAddress loopback = InetAddress.getByAddress(new byte[] {127, 0, 0, 1});
            s = new DatagramSocket(new InetSocketAddress(loopback, port));
        } catch (IOException e) {
            System.out.println("WARNING: camera panel disabled, UDP 127.0.0.1:" + port
                    + " is unavailable (" + e.getMessage() + ").");
        }
        this.socket = s;
    }

    /** Starts the background receive thread. Does nothing if the port was not bound. */
    public void start() {
        if (socket == null) {
            return;
        }
        Thread thread = new Thread(this::receiveLoop, "udp-camera-feed");
        thread.setDaemon(true);
        thread.start();
    }

    private void receiveLoop() {
        byte[] buffer = new byte[128 * 1024];
        while (true) {
            DatagramPacket packet = new DatagramPacket(buffer, buffer.length);
            try {
                socket.receive(packet);
            } catch (IOException e) {
                return; // socket closed: the game is shutting down
            }
            try {
                BufferedImage image = ImageIO.read(
                        new ByteArrayInputStream(packet.getData(), packet.getOffset(), packet.getLength()));
                if (image != null) {
                    onFrame.accept(image);
                }
            } catch (IOException e) {
                // a damaged frame: skip it
            }
        }
    }

    /** Panel that shows the latest camera frame. Safe to update from any thread. */
    public static class CameraPanel extends JPanel {
        private volatile BufferedImage frame;

        public CameraPanel(int width, int height) {
            setPreferredSize(new Dimension(width, height));
            setBackground(Color.BLACK);
        }

        public void setFrame(BufferedImage image) {
            this.frame = image;
            repaint();
        }

        @Override
        protected void paintComponent(Graphics g) {
            super.paintComponent(g);
            BufferedImage current = frame;
            if (current == null) {
                g.setColor(Color.WHITE);
                g.setFont(new Font("Arial", Font.PLAIN, 14));
                String text = "Waiting for the camera...";
                int textWidth = g.getFontMetrics().stringWidth(text);
                g.drawString(text, (getWidth() - textWidth) / 2, getHeight() / 2);
                return;
            }
            g.drawImage(current, 0, 0, getWidth(), getHeight(), null);
        }
    }
}
