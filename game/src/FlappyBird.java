import java.awt.*;
import java.awt.event.*;
import java.util.ArrayList;
import javax.swing.*;

public class FlappyBird extends JPanel implements ActionListener, KeyListener {
    int boardWidth = 360;
    int boardHeight = 640;

    
    Image backgroundImg;
    Image birdImg;
    Image topPipeImg;
    Image bottomPipeImg;


    class Bird {
        int x = boardWidth/8;
        int y = boardHeight/2;
        int width = 34;
        int height = 24;
        Image img;

        Bird(Image img) {
            this.img = img;
        }
    }

    //pipe class
    int pipeX = boardWidth;
    int pipeY = 0;
    int pipeWidth = 64;  // 1/6
    int pipeHeight = 512;
    
    class Pipe {
        int x = pipeX;
        int y = pipeY;
        int width = pipeWidth;
        int height = pipeHeight;
        Image img;
        boolean passed = false;

        Pipe(Image img) {
            this.img = img;
        }
    }

    //game logic
    Bird bird;
    int velocityX = -4; 
    int velocityY = 0; 
    int gravity = 1;

    ArrayList<Pipe> pipes;
    

    Timer gameLoop;
    Timer placePipeTimer;
    boolean gameOver = false;
    double score = 0;
    JFrame gameOverFrame; // kept so a restart can close the game-over window
    long gameOverAt = 0; // when the game ended (ms), used by the FLAP lockout
    static final int GAME_OVER_FLAP_LOCKOUT_MS = 800;

    FlappyBird() {
        setPreferredSize(new Dimension(boardWidth, boardHeight));

        setFocusable(true); 
        addKeyListener(this);

        backgroundImg = new ImageIcon(getClass().getResource("./flappybirdbg.png")).getImage();
        birdImg = new ImageIcon(getClass().getResource("./flappybird.png")).getImage();
        topPipeImg = new ImageIcon(getClass().getResource("./toppipe.png")).getImage();
        bottomPipeImg = new ImageIcon(getClass().getResource("./bottompipe.png")).getImage();

    
        bird = new Bird(birdImg);

        pipes = new ArrayList<Pipe>();


        placePipeTimer = new Timer(1500, new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
            
              placePipes();
            }
        });
        placePipeTimer.start();
        

		gameLoop = new Timer(1000/60, this); 
        gameLoop.start();
	}
    
    void placePipes() {
        //  -pipeHeight/4 ->   -3/4 pipeHeight
        int randomPipeY = (int) (pipeY - pipeHeight/4 - Math.random()*(pipeHeight/2));
        int openingSpace = boardHeight/4;
    
        Pipe topPipe = new Pipe(topPipeImg);
        topPipe.y = randomPipeY;
        pipes.add(topPipe);
    
        Pipe bottomPipe = new Pipe(bottomPipeImg);
        bottomPipe.y = topPipe.y  + pipeHeight + openingSpace;
        pipes.add(bottomPipe);
    }
    
    
    public void paintComponent(Graphics g) {
	super.paintComponent(g); 
		draw(g);
	}

	public void draw(Graphics g) {
        
        g.drawImage(backgroundImg, 0, 0, this.boardWidth, this.boardHeight, null);

        g.drawImage(birdImg, bird.x, bird.y, bird.width, bird.height, null);
  

     //pipes
        for (int i = 0; i < pipes.size(); i++) {
            Pipe pipe = pipes.get(i);
            g.drawImage(pipe.img, pipe.x, pipe.y, pipe.width, pipe.height, null);
        }

        //score
        g.setColor(Color.white);

        g.setFont(new Font("Arial", Font.PLAIN, 32));
        if (!gameOver) {
            g.drawString(String.valueOf((int) score), 10, 35);
        }
        
        
	}

    public void move() {
        //bird
        velocityY += gravity;
        bird.y += velocityY;
        bird.y = Math.max(bird.y, 0);

        //pipes
        for (int i = 0; i < pipes.size(); i++) {
            Pipe pipe = pipes.get(i);
            pipe.x += velocityX;

            if (!pipe.passed && bird.x > pipe.x + pipe.width) {
                score += 0.5; // 0.5*2 = 1
                pipe.passed = true;
            }

            if (collision(bird, pipe)) {
                gameOver = true;
            }
        }

        if (bird.y > boardHeight) {
            gameOver = true;
        }
    }

    boolean collision(Bird a, Pipe b) {
        return a.x < b.x + b.width &&   //a's top left corner doesn't reach b's top right corner
               a.x + a.width > b.x &&   //a's top right corner passes b's top left corner
               a.y < b.y + b.height &&  //a's top left corner doesn't reach b's bottom left corner
               a.y + a.height > b.y;    //a's bottom left corner passes b's top left corner
    }

    
    @Override
    public void actionPerformed(ActionEvent e) { 
       
        move();
        repaint();
        if (gameOver) {
            gameOverAt = System.currentTimeMillis();
            placePipeTimer.stop();
            gameLoop.stop();
            showGameOverFrame();
        }
    }  

    @Override
    public void keyPressed(KeyEvent e) {
        if (e.getKeyCode() == KeyEvent.VK_SPACE) {

            jump();
           

        }
    }

    @Override
    public void keyTyped(KeyEvent e) {}

    @Override
    public void keyReleased(KeyEvent e) {}

    // One flap: the same action SPACE performs.
    void jump() {
        velocityY = -9;
    }

    // Reset everything and start playing again (used by the Restart button).
    void restartGame() {
        bird.x = boardWidth / 8;
        bird.y = boardHeight / 2;
        velocityY = 0;
        pipes.clear();
        score = 0;
        gameOver = false;

        gameLoop.start();
        placePipeTimer.start();
        if (gameOverFrame != null) {
            gameOverFrame.dispose();
            gameOverFrame = null;
        }
        repaint();
        requestFocusInWindow();
    }

    // A FLAP from the webcam: jump, or restart if the game is over.
    void handleFlap() {
        if (gameOver) {
            // Ignore the flap that may have ended the game so it can't restart it instantly.
            if (System.currentTimeMillis() - gameOverAt < GAME_OVER_FLAP_LOCKOUT_MS) {
                return;
            }
            restartGame();
        } else {
            jump();
        }
    }

    private void showGameOverFrame() {
        gameOverFrame = new JFrame("Game Over");
        gameOverFrame.setSize(300, 200);
        gameOverFrame.setLayout(new BorderLayout());
        gameOverFrame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
    
        JLabel gameOverLabel = new JLabel("Game Over! Score: " + (int) score, SwingConstants.CENTER);
        gameOverLabel.setFont(new Font("Arial", Font.BOLD, 20));
        gameOverLabel.setForeground(Color.RED);
    
        JButton restartButton = new JButton("Restart");
        restartButton.addActionListener(e -> restartGame());
    
        gameOverFrame.add(gameOverLabel, BorderLayout.CENTER);
        gameOverFrame.add(restartButton, BorderLayout.SOUTH);
    
        gameOverFrame.setLocationRelativeTo(null);
        gameOverFrame.setVisible(true);
    }
}